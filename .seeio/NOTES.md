# Site notes

## What this site is
A personal professional portfolio (one page, static HTML/CSS/JS served by busybox httpd).

## Confirmed facts
- Customer asked for a portfolio site to present their professional work. (2026-08-23)

## Open questions (asked, awaiting answers)
- Full name, professional title, city/country
- Field of work and main services
- 3 projects to feature (brief, role, outcome)
- Work history / education for the timeline
- Contact email, phone, LinkedIn or other profiles
- Photo and project images
- Language of the site (currently English)
- Any testimonials to include

## Decisions
- Structure: hero, about, services, selected work, experience timeline, testimonials, contact.
- Placeholder copy is in place until the customer supplies real details.
- No em dashes in visitor-facing copy.
- Fonts: Fraunces (headings) + Inter (body) via Google Fonts.
- CSS/JS linked with ?v= query for cache busting; bump on every change.
