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
- Owner inbox at /inbox. FIRST VISIT SETS THE PASSWORD, so the owner must claim it right after the first deploy.
  Session is an HMAC-signed cookie; the signing key lives at /data/session.key. Password stored as PBKDF2-SHA256 (200k rounds).
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
- Cache busting: /style.css?v=3 and /app.js?v=3. BUMP THE VERSION on every CSS/JS change, in every page that links them
  (index, 404, three case studies, and the inline inbox template in main.py).

## Open questions
- Professional photo (GitHub avatar is the default identicon, so the hero uses a "VK" monogram and a code card).
- Screenshots of Task-Flow, Route-Master and SaaS Pulse for the case studies.
- Client testimonials to add (no testimonials section on the page yet).
- Confirm the case study wording is accurate before sending it to recruiters.
