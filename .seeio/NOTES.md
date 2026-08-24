# Site notes

## What this site is
Portfolio for Vishal Kumar, full stack developer. FastAPI serves a static multi-page site from `public/`
plus a working contact form. Homepage + three project case studies + 404.

## Confirmed facts (customer's resume + GitHub, 2026-08-23)
- Name: Vishal Kumar. Title: Full Stack Developer (Next.js & MERN, SaaS & AI integration).
- Location: Sukkur, Pakistan (UTC+5). Open to full-time remote, contract and freelance work worldwide.
- Email: vishall.kandharee@gmail.com | Phone/WhatsApp: +92 300 0249930
- GitHub: https://github.com/VISHALLkandharee (17 public repos) | LinkedIn: https://www.linkedin.com/in/vishal-kumar-87a19730b/
- Education: B.Sc. Artificial Intelligence, Szabist University Hyderabad, CGPA 3.71/4.00, expected 2026. Top GPA Scholarship, 2nd semester.
- Experience: freelance full stack developer 2023 to present (Fiverr, Facebook dev groups, WhatsApp referrals), 10+ client projects.
- Languages: English (professional), Urdu/Hindi (fluent), Sindhi (native).
- Live projects: Task-Flow, Route-Master, SaaS Pulse, InvestTrack, Room Finder, Habit Tracker.
- Resume PDF at public/assets/Vishal-Kumar-Resume.pdf, linked for download in several places.

## Architecture
- `main.py` (FastAPI) + `public/` static files. Healthcheck: /healthz.
- Contact form POSTs to /api/contact, stored in SQLite at /data/app.db (created on first boot, /data is the only persistent path).
- Owner inbox at /inbox, reachable from the "Inbox" link in the footer of every page (rel=nofollow, noindex,
  disallowed in robots.txt). Once signed in, a floating "Inbox (n)" badge appears on the public pages; it is driven by a
  readable `vk_owner` marker cookie plus GET /api/inbox/unread, which requires a real session, so the marker grants nothing.
  Signing out bumps a `session_epoch` setting, which retires every token already issued.
- Owner inbox at /inbox. FIRST VISIT SETS THE PASSWORD, so the owner must claim it right after the first deploy.
  Session is an HMAC-signed cookie; the signing key lives at /data/session.key. Password stored as PBKDF2-SHA256 (200k rounds).
- Contact form works without JavaScript too: the form posts normally, the server redirects to /thanks.html on success
  and renders a readable error page on failure. With JS it submits through fetch (X-Requested-With: fetch) and stays in place.
- Spam handling: hidden honeypot field, server-side validation, per-IP rate limit (8/hour when X-Forwarded-For identifies
  the visitor, 60/hour shared fallback when it does not).
- /inbox is disallowed in robots.txt and marked noindex.

## Design decisions
- Dark by default with a light theme toggle (localStorage key `vk-theme`, respects prefers-color-scheme).
- Teal (#2dd4bf) to periwinkle (#7c9cff) accents, Inter + JetBrains Mono, ambient orbs + grid background.
- Motion: scroll progress bar, reveal-on-scroll, typed role line, count-up stats, pointer glow on project cards.
  All motion is disabled under prefers-reduced-motion.
- Case study copy is grounded in the resume bullets and repo descriptions. No invented metrics.
- No em dashes anywhere in visitor-facing copy.
- Reveal animations only apply when JS is present (`html.js` class), so content is never hidden if a script fails.
- Cache busting: /style.css?v=5 and /app.js?v=5. BUMP THE VERSION on every CSS/JS change, in every page that links them
  (index, 404, three case studies, and the inline inbox template in main.py).

## Incident, 2026-08-24: contact form looked unresponsive
- Cause: app.js changed without bumping its ?v= query, so returning visitors ran a cached older script.
  That script sent no fetch marker, the server answered a plain form POST with a 303 to /thanks.html,
  the script could not parse the HTML and showed nothing useful.
- Fixes: assets bumped to v=4; the server now recognises a background request from several signals
  (X-Requested-With, Accept, Sec-Fetch-Dest, Sec-Fetch-Mode), so even an outdated script gets JSON;
  the client treats any successful response as delivered even if the body is not JSON.
- Also added: a success panel that replaces the form, scrolls into view and offers one-tap
  "send it on WhatsApp / by email too" handoff so a visitor can reach Vishal instantly.
- LESSON: bump ?v= in the SAME commit as any CSS/JS change, in all five pages and in main.py.

## Open questions
- Professional photo (GitHub avatar is the default identicon, so the hero uses a "VK" monogram and a code card).
- Screenshots of Task-Flow, Route-Master and SaaS Pulse for the case studies.
- Client testimonials to add (no testimonials section on the page yet).
- Email notification for new contact messages: would need SMTP or an API key, which cannot live in this
  repo. Owner reads messages at /inbox for now, and visitors can hand off to WhatsApp or email in one tap.
- Confirm the case study wording is accurate before sending it to recruiters.
