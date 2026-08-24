"""Vishal Kumar portfolio.

Static site served by FastAPI, plus a working contact form.

see.io contract notes:
  * /data is the ONLY path that survives deploys and rollbacks;
  * builds and build sandboxes see /data empty or absent, so everything
    stateful is created on first boot;
  * nothing stateful is written anywhere else.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
from urllib.parse import quote
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "app.db"
SECRET_PATH = DATA_DIR / "session.key"

SESSION_COOKIE = "vk_inbox"
OWNER_MARKER = "vk_owner"   # readable by the page, grants nothing on its own
SESSION_TTL = 60 * 60 * 12  # 12 hours

MAX_NAME = 120
MAX_EMAIL = 160
MAX_SUBJECT = 160
MAX_MESSAGE = 4000
# The owner password is set at build time and only its PBKDF2 hash is stored
# here, so the repository holds no usable secret. The owner can replace it from
# inside the inbox, which writes a new hash to /data and takes precedence.
BOOTSTRAP_PASSWORD_HASH = "6fb196411648659784f814c1e9ee0460$7f8d88bd6303c61986f81db1d20c18609f3c231bbd789287d2ef4138d1b06c41"

LOGIN_WINDOW = 900
LOGIN_MAX_ATTEMPTS = 10
GLOBAL_RATE_MAX = 120     # total contact messages accepted per window
MAX_STORED_MESSAGES = 5000

RATE_LIMIT_WINDOW = 3600
RATE_LIMIT_MAX = 8          # per visitor IP, when the proxy identifies it
RATE_LIMIT_MAX_SHARED = 60  # fallback when every request looks like one IP

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """First-boot initialization: /data may be empty or absent here."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as conn, conn:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error:
            pass  # a read-only volume still allows reads in the default mode
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                name     TEXT NOT NULL,
                email    TEXT NOT NULL,
                subject  TEXT NOT NULL DEFAULT '',
                body     TEXT NOT NULL,
                ip_hash  TEXT NOT NULL DEFAULT '',
                read     INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_hex(32), encoding="utf-8")

    # One-time migration. An earlier version let the first visitor to /inbox
    # set the owner password, so any password already stored could have been
    # set by a stranger. Retire it once, then never again: a password the
    # owner sets from inside the inbox is written after this flag exists.
    with closing(connect()) as conn, conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'credential_version'"
        ).fetchone()
        if row is None or row["value"] != "2":
            conn.execute("DELETE FROM settings WHERE key = 'owner_password'")
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('credential_version', '2') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )


def session_secret() -> bytes:
    if not SECRET_PATH.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SECRET_PATH.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode()


def get_setting(key: str) -> str | None:
    with closing(connect()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# --------------------------------------------------------------------------
# owner auth for /inbox
# --------------------------------------------------------------------------
def owner_hash() -> str:
    """The password set from inside the inbox wins; otherwise the build-time one."""
    try:
        stored = get_setting("owner_password")
    except sqlite3.Error:
        stored = None
    return stored or BOOTSTRAP_PASSWORD_HASH


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def session_epoch() -> str:
    """Bumped on sign-out, which invalidates every token issued before it."""
    epoch = get_setting("session_epoch")
    if epoch is None:
        epoch = "1"
        set_setting("session_epoch", epoch)
    return epoch


def make_session() -> str:
    payload = f"{int(time.time()) + SESSION_TTL}.{session_epoch()}"
    sig = hmac.new(session_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def valid_session(token: str | None) -> bool:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return False
    expires, epoch, sig = parts
    expected = hmac.new(session_secret(), f"{expires}.{epoch}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    if epoch != session_epoch():
        return False
    try:
        return int(expires) > time.time()
    except ValueError:
        return False


def client_ip_hash(request: Request) -> tuple[str, int]:
    """Identify the sender, and say how strict the rate limit may be.

    Behind the platform proxy every request can carry the same source
    address. If nothing distinguishes visitors, a tight per-IP limit would
    lock out real people, so the cap loosens instead.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        ip, limit = fwd.split(",")[0].strip(), RATE_LIMIT_MAX
    else:
        ip, limit = (request.client.host if request.client else ""), RATE_LIMIT_MAX_SHARED
    return hashlib.sha256((ip + "vk-portfolio").encode()).hexdigest()[:32], limit


# --------------------------------------------------------------------------
# app
# --------------------------------------------------------------------------
DB_READY = True


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201 - FastAPI lifespan signature
    global DB_READY
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001 - never block startup on storage
        DB_READY = False
        print(f"[startup] database unavailable, serving the site read-only: {exc!r}")
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=800)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # noqa: ANN001
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    # Everything the site needs comes from this origin. The inline theme script
    # and the inline styles in the markup need 'unsafe-inline'; no third party
    # script can run, which is the attack this actually blocks.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'",
    )
    if request.url.path.startswith(("/inbox", "/api/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/contact")
def contact(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    subject: str = Form(""),
    message: str = Form(""),
    website: str = Form(""),  # honeypot: real people leave it empty
) -> Response:
    # A browser labels its own requests: a normal form navigation is
    # sec-fetch-dest=document, while fetch()/XHR is dest=empty, mode=cors.
    # Checking several signals means an outdated cached script still gets
    # JSON back rather than a redirect it cannot parse.
    wants_json = (
        request.headers.get("x-requested-with", "").lower() in {"fetch", "xmlhttprequest"}
        or "application/json" in request.headers.get("accept", "").lower()
        or request.headers.get("sec-fetch-dest", "").lower() == "empty"
        or request.headers.get("sec-fetch-mode", "").lower() == "cors"
    )

    def reply(payload: dict, status_code: int = 200) -> Response:
        """JSON for the fetch path, a readable page when JavaScript is off."""
        if wants_json:
            return JSONResponse(payload, status_code=status_code)
        if payload.get("ok"):
            return RedirectResponse("/thanks.html", status_code=303)
        problems = list((payload.get("errors") or {}).values())
        if not problems and payload.get("error"):
            problems = [payload["error"]]
        detail = "".join(f"<li>{html.escape(p)}</li>" for p in problems)
        body = (
            '<div class="inbox"><h1 style="font-size:1.8rem">That did not go through</h1>'
            f'<ul style="margin:18px 0;color:var(--muted)">{detail}</ul>'
            '<p class="note">Go back and try again, or email '
            '<a href="mailto:vishall.kandharee@gmail.com" style="color:var(--accent)">'
            'vishall.kandharee@gmail.com</a> directly.</p>'
            '<p style="margin-top:22px"><a class="btn btn-ghost" href="/#contact">Back to the form</a></p></div>'
        )
        response = page("Message not sent", body)
        response.status_code = status_code
        return response

    if website.strip():
        # Silently accept and drop: bots get a 200, the inbox stays clean.
        return reply({"ok": True})

    name = name.strip()[:MAX_NAME]
    email = email.strip()[:MAX_EMAIL]
    subject = subject.strip()[:MAX_SUBJECT]
    message = message.strip()[:MAX_MESSAGE]

    errors: dict[str, str] = {}
    if len(name) < 2:
        errors["name"] = "Please tell me your name."
    if not EMAIL_RE.match(email):
        errors["email"] = "That email address does not look right."
    if len(message) < 10:
        errors["message"] = "A sentence or two about the project, please."
    if errors:
        return reply({"ok": False, "errors": errors}, status_code=422)

    ip_hash, rate_max = client_ip_hash(request)
    cutoff = str(int(time.time()) - RATE_LIMIT_WINDOW)
    busy = "Too many messages just now. Please email vishall.kandharee@gmail.com directly."
    try:
        with closing(connect()) as conn, conn:
            (recent,) = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE ip_hash = ? AND strftime('%s', ts) > ?",
                (ip_hash, cutoff),
            ).fetchone()
            if recent >= rate_max:
                return reply({"ok": False, "error": busy}, status_code=429)

            # A spoofed X-Forwarded-For gives an attacker a fresh per-IP bucket
            # every request, so an absolute ceiling backs the per-sender one up.
            (window_total,) = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE strftime('%s', ts) > ?", (cutoff,)
            ).fetchone()
            if window_total >= GLOBAL_RATE_MAX:
                return reply({"ok": False, "error": busy}, status_code=429)

            # Never let the table grow without bound on the persistent volume.
            (stored,) = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            if stored >= MAX_STORED_MESSAGES:
                conn.execute(
                    "DELETE FROM messages WHERE id IN ("
                    "  SELECT id FROM messages WHERE read = 1 ORDER BY id ASC LIMIT 100)"
                )
                (stored,) = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
                if stored >= MAX_STORED_MESSAGES:
                    return reply({"ok": False, "error": busy}, status_code=429)

            conn.execute(
                "INSERT INTO messages (name, email, subject, body, ip_hash) VALUES (?, ?, ?, ?, ?)",
                (name, email, subject, message, ip_hash),
            )
    except sqlite3.Error as exc:
        print(f"[contact] storage failure: {exc!r}")
        return reply(
            {"ok": False, "error": "I could not save that just now. Please email "
                                   "vishall.kandharee@gmail.com or message +92 300 0249930 on WhatsApp."},
            status_code=503,
        )
    return reply({"ok": True})


# --------------------------------------------------------------------------
# owner inbox
# --------------------------------------------------------------------------
def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="/fonts.css?v=2">
<link rel="stylesheet" href="/style.css?v=8">
<style>
 body{{padding:40px 0}}
 .inbox{{max-width:860px;margin:0 auto;padding:0 24px}}
 .inbox form{{display:grid;gap:14px;max-width:420px;margin-top:22px}}
 .inbox input{{padding:13px 15px;border-radius:12px;border:1px solid var(--line);
   background:var(--surface);color:var(--text);font:inherit}}
 .msg{{border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:16px;background:var(--surface)}}
 .msg.unread{{border-color:var(--accent)}}
 .msg h3{{font-size:1.05rem;margin-bottom:4px}}
 .msg .meta{{font-size:.82rem;color:var(--muted);margin-bottom:12px}}
 .msg p.body{{white-space:pre-wrap;color:var(--text);font-size:.96rem}}
 .msg .row{{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}}
 .note{{color:var(--muted);font-size:.9rem;margin-top:10px}}
 .reveal-pw{{display:flex;align-items:center;gap:9px;font-size:.88rem;color:var(--muted);cursor:pointer}}
 .reveal-pw input{{width:auto;margin:0;accent-color:var(--accent)}}
</style></head><body>{body}</body></html>"""
    )


def sign_in(response: Response) -> None:
    """Signed session cookie, plus a plain marker the site itself can read."""
    response.set_cookie(
        SESSION_COOKIE, make_session(), httponly=True, secure=True,
        samesite="lax", max_age=SESSION_TTL, path="/",
    )
    response.set_cookie(
        OWNER_MARKER, "1", secure=True, samesite="lax", max_age=SESSION_TTL, path="/"
    )


@app.get("/api/inbox/unread")
def unread_count(request: Request) -> JSONResponse:
    """Feeds the owner badge on the public pages. Requires a real session."""
    if not valid_session(request.cookies.get(SESSION_COOKIE)):
        return JSONResponse({"signedIn": False, "unread": 0}, status_code=401)
    try:
        with closing(connect()) as conn:
            (unread,) = conn.execute("SELECT COUNT(*) FROM messages WHERE read = 0").fetchone()
    except sqlite3.Error:
        return JSONResponse({"signedIn": True, "unread": 0})
    return JSONResponse({"signedIn": True, "unread": int(unread)})


def csrf_token(session: str) -> str:
    """Per-session token, so an inbox action cannot be triggered cross-site."""
    return hmac.new(session_secret(), f"csrf.{session}".encode(), hashlib.sha256).hexdigest()[:32]


def csrf_ok(request: Request, submitted: str) -> bool:
    session = request.cookies.get(SESSION_COOKIE) or ""
    return bool(submitted) and hmac.compare_digest(submitted, csrf_token(session))


def login_allowed(bucket: str) -> bool:
    """Throttle password guessing, which is also expensive to verify."""
    now = time.time()
    attempts = [t for t in LOGIN_ATTEMPTS.get(bucket, []) if now - t < LOGIN_WINDOW]
    LOGIN_ATTEMPTS[bucket] = attempts
    if len(LOGIN_ATTEMPTS) > 5000:  # keep the table from growing without bound
        LOGIN_ATTEMPTS.clear()
    return len(attempts) < LOGIN_MAX_ATTEMPTS


def login_seen(bucket: str) -> None:
    LOGIN_ATTEMPTS.setdefault(bucket, []).append(time.time())


LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def login_page(note: str = "") -> HTMLResponse:
    warning = f'<p class="note" style="color:#ff8b8b">{html.escape(note)}</p>' if note else ""
    return page(
        "Inbox",
        f"""<div class="inbox">
<h1 style="font-size:1.9rem">Inbox</h1>
<p class="note">Messages sent through the contact form on the site.</p>
{warning}
<form method="post" action="/inbox/login">
  <input id="pw" type="password" name="password" placeholder="Password" required autofocus
         autocomplete="current-password" autocapitalize="none" autocorrect="off" spellcheck="false">
  <label class="reveal-pw"><input type="checkbox" id="show-pw"> Show what I typed</label>
  <button class="btn btn-primary" type="submit">Sign in</button>
</form>
<p class="note" style="margin-top:18px">The password is all lower case, and deliberately contains no
look-alike characters: no letter i, l or o, and no digit 0 or 1. Tick the box above to check what you typed.</p>
<script>
  document.getElementById('show-pw').addEventListener('change', function () {{
    document.getElementById('pw').type = this.checked ? 'text' : 'password';
  }});
</script>
<p class="note" style="margin-top:22px"><a href="/" style="color:var(--accent)">Back to the site</a></p></div>""",
    )


@app.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request) -> HTMLResponse:
    session = request.cookies.get(SESSION_COOKIE)
    if not valid_session(session):
        return login_page()

    token = csrf_token(session or "")
    try:
        with closing(connect()) as conn:
            rows = conn.execute(
                "SELECT id, ts, name, email, subject, body, read FROM messages "
                "ORDER BY id DESC LIMIT 200"
            ).fetchall()
            (unread,) = conn.execute("SELECT COUNT(*) FROM messages WHERE read = 0").fetchone()
    except sqlite3.Error as exc:
        return page(
            "Inbox",
            f"""<div class="inbox"><h1 style="font-size:1.9rem">Inbox</h1>
<p class="note">The message store is temporarily unavailable ({html.escape(type(exc).__name__)}).
The rest of the site is unaffected. Try again shortly.</p>
<p style="margin-top:20px"><a class="btn btn-ghost" href="/">Back to the site</a></p></div>""",
        )

    items = []
    for r in rows:
        raw_subject = r["subject"] or "(no subject)"
        subject = html.escape(raw_subject)
        items.append(
            f"""<article class="msg{' unread' if not r['read'] else ''}">
  <h3>{subject}</h3>
  <p class="meta">{html.escape(r['name'])} &lt;{html.escape(r['email'])}&gt; · {html.escape(r['ts'])} UTC</p>
  <p class="body">{html.escape(r['body'])}</p>
  <div class="row">
    <a class="btn btn-primary btn-sm" href="mailto:{quote(r['email'])}?subject={quote('Re: ' + raw_subject)}">Reply</a>
    <form method="post" action="/inbox/read/{r['id']}"><input type="hidden" name="csrf" value="{token}">
      <button class="btn btn-ghost btn-sm" type="submit">{'Mark unread' if r['read'] else 'Mark read'}</button></form>
    <form method="post" action="/inbox/delete/{r['id']}"><input type="hidden" name="csrf" value="{token}">
      <button class="btn btn-ghost btn-sm" type="submit">Delete</button></form>
  </div>
</article>"""
        )
    body = "".join(items) or '<p class="note">No messages yet. Anything sent through the contact form lands here.</p>'
    return page(
        "Inbox",
        f"""<div class="inbox">
<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap">
  <h1 style="font-size:1.9rem">Inbox <span class="accent">({unread} unread)</span></h1>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <a class="btn btn-ghost btn-sm" href="/">Back to site</a>
    <a class="btn btn-ghost btn-sm" href="/inbox/password">Change password</a>
    <form method="post" action="/inbox/logout"><input type="hidden" name="csrf" value="{token}">
      <button class="btn btn-ghost btn-sm" type="submit">Sign out</button></form>
  </div>
</div>{body}</div>""",
    )


@app.post("/inbox/login")
def inbox_login(request: Request, password: str = Form("")) -> Response:
    password = password.strip()  # pasted passwords often carry a space or newline
    bucket, _ = client_ip_hash(request)
    if not login_allowed(bucket):
        return login_page("Too many attempts. Wait a few minutes and try again.")
    if verify_password(password, owner_hash()):
        LOGIN_ATTEMPTS.pop(bucket, None)  # only failures count towards the throttle
        response = RedirectResponse("/inbox", status_code=303)
        sign_in(response)
        return response
    login_seen(bucket)
    return login_page("That password is not right. Tick \"Show what I typed\" to check it, and remember it is all lower case.")


@app.get("/inbox/password", response_class=HTMLResponse)
def password_form(request: Request) -> HTMLResponse:
    session = request.cookies.get(SESSION_COOKIE)
    if not valid_session(session):
        return login_page()
    return page(
        "Change password",
        f"""<div class="inbox">
<h1 style="font-size:1.9rem">Change password</h1>
<p class="note">The new password is stored as a hash on the persistent volume and replaces the one set at build time.</p>
<form method="post" action="/inbox/password">
  <input type="hidden" name="csrf" value="{csrf_token(session or '')}">
  <input type="password" name="current" placeholder="Current password" required autocomplete="current-password">
  <input type="password" name="password" placeholder="New password (10 characters or more)" minlength="10" required autocomplete="new-password">
  <input type="password" name="confirm" placeholder="Repeat the new password" minlength="10" required autocomplete="new-password">
  <button class="btn btn-primary" type="submit">Save new password</button>
</form>
<p class="note" style="margin-top:22px"><a href="/inbox" style="color:var(--accent)">Back to the inbox</a></p></div>""",
    )


@app.post("/inbox/password")
def password_change(
    request: Request,
    current: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
    csrf: str = Form(""),
) -> Response:
    current, password, confirm = current.strip(), password.strip(), confirm.strip()
    session = request.cookies.get(SESSION_COOKIE)
    if not valid_session(session) or not csrf_ok(request, csrf):
        return login_page()
    if not verify_password(current, owner_hash()):
        return page("Change password", '<div class="inbox"><p class="note">The current password is not right. '
                    '<a href="/inbox/password" style="color:var(--accent)">Try again</a>.</p></div>')
    if len(password) < 10 or password != confirm:
        return page("Change password", '<div class="inbox"><p class="note">The new passwords must match and be at '
                    'least 10 characters. <a href="/inbox/password" style="color:var(--accent)">Try again</a>.</p></div>')
    try:
        set_setting("owner_password", hash_password(password))
    except sqlite3.Error:
        return page("Change password", '<div class="inbox"><p class="note">Could not save the new password just now. '
                    'Please try again shortly.</p></div>')
    return RedirectResponse("/inbox", status_code=303)


@app.post("/inbox/logout")
def inbox_logout(request: Request, csrf: str = Form("")) -> Response:
    response = RedirectResponse("/inbox", status_code=303)
    if valid_session(request.cookies.get(SESSION_COOKIE)) and csrf_ok(request, csrf):
        # Retiring the epoch invalidates every token already issued.
        try:
            set_setting("session_epoch", str(int(session_epoch()) + 1))
        except sqlite3.Error:
            pass
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(OWNER_MARKER, path="/")
    return response


@app.post("/inbox/read/{message_id}")
def inbox_read(message_id: int, request: Request, csrf: str = Form("")) -> Response:
    if valid_session(request.cookies.get(SESSION_COOKIE)) and csrf_ok(request, csrf):
        try:
            with closing(connect()) as conn, conn:
                conn.execute("UPDATE messages SET read = 1 - read WHERE id = ?", (message_id,))
        except sqlite3.Error:
            pass
    return RedirectResponse("/inbox", status_code=303)


@app.post("/inbox/delete/{message_id}")
def inbox_delete(message_id: int, request: Request, csrf: str = Form("")) -> Response:
    if valid_session(request.cookies.get(SESSION_COOKIE)) and csrf_ok(request, csrf):
        try:
            with closing(connect()) as conn, conn:
                conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        except sqlite3.Error:
            pass
    return RedirectResponse("/inbox", status_code=303)


# --------------------------------------------------------------------------
# static site (mounted last so the routes above win)
# --------------------------------------------------------------------------
class CachedStatic(StaticFiles):
    """Serve the site with explicit caching rules.

    Without a Cache-Control header a browser is free to invent its own
    freshness lifetime, so an updated page can stay invisible to someone who
    visited before. HTML therefore always revalidates (cheap: the ETag
    usually turns it into a 304), while CSS and JS are versioned by a ?v=
    query and can be held for a week.
    """

    async def get_response(self, path: str, scope):  # noqa: ANN001, ANN201
        response = await super().get_response(path, scope)
        lowered = path.lower()
        if lowered.endswith((".html", "/")) or "." not in lowered.rsplit("/", 1)[-1]:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif lowered.endswith((".css", ".js")):
            response.headers["Cache-Control"] = "public, max-age=604800"
        elif lowered.endswith((".woff2", ".woff")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif lowered.endswith((".pdf", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico")):
            response.headers["Cache-Control"] = "public, max-age=86400"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response

@app.exception_handler(404)
async def not_found(request: Request, exc) -> Response:  # noqa: ANN001
    target = PUBLIC_DIR / "404.html"
    if target.exists():
        return FileResponse(target, status_code=404)
    return HTMLResponse("Not found", status_code=404)


app.mount("/", CachedStatic(directory=PUBLIC_DIR, html=True), name="site")
