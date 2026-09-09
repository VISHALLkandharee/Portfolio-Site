Deployment guide — Railway (backend) + Vercel (frontend)

Goal
- Host the full site exactly as it worked on see.io: static site plus working contact form and owner inbox.
- Frontend on Vercel (fast CDN). Backend (FastAPI + SQLite) on Railway with a persistent volume mounted at `/data` so the inbox and messages persist.

What we changed in the repo
- `main.py`: optional CORS support via `CORS_ALLOW_ORIGINS` env var (comma-separated origins).
- `Dockerfile`: uses `${PORT:-8080}` so Railway or other hosts can inject the runtime port.

Railway — deploy the full Python app (preserves contact form + inbox)
1. Create a new Railway project and choose "Deploy from GitHub" → select this repository.
2. Add a new Service → choose "Web Service" and connect the repo.
   - Preferred: use the included `Dockerfile`. Railway will build the image.
   - Alternative (no Docker): choose "Python" and set the Start Command to:
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
3. Persistent volume (required):
   - Create a Volume (Persistent Disk) in Railway and mount it at path `/data` for the service.
   - This ensures `app.db` and `session.key` persist across restarts/deploys.
4. Public domain / Generate URL:
   - In Service Settings → Networking → Generate Service Domain, enter `8080` as the target port (the app listens on 8080 by default inside the container).
   - Click "Generate Domain". Railway will show a public URL like `https://portfolio-site-production-xxxx.up.railway.app`.
5. Environment variables (Railway service settings):
   - `CORS_ALLOW_ORIGINS` (optional): set to your Vercel origin once the frontend is deployed, for example:
     ```text
     https://your-vercel-app.vercel.app
     ```
     Multiple origins: comma-separated.
   - `DATA_DIR`: leave unset (defaults to `/data`) unless you want a custom path.
6. Deploy and verify:
   - Visit `https://<railway-domain>/healthz` → should respond `{"ok": true}`.
   - Visit `https://<railway-domain>/` → serves the static site and API endpoints.
   - Inbox lives at `https://<railway-domain>/inbox` (use the owner password flow to sign in).

Vercel — deploy the static frontend
1. In Vercel, Import Project → select this GitHub repo.
2. Configure for a static site:
   - Root Directory: `/` (repo root)
   - Framework Preset: `Other` or `Static Site`
   - Build Command: leave empty
   - Output Directory: `public`
3. Deploy. Vercel will provide a URL like `https://your-vercel-app.vercel.app`.
4. Connect the frontend to the Railway backend (pick one):
   - Recommended (no code change): set `CORS_ALLOW_ORIGINS` on Railway to the Vercel origin (see above). The frontend uses relative `/api/*` calls and will be allowed by CORS.
   - Alternative (code change): replace relative fetch paths in `public/app.js` and `public/index.html` to point directly to the Railway domain (e.g. `https://<railway>/api/contact`). I can patch these for you if you prefer this approach.

Local testing (recommended before deploy)
1. Create a local data folder and set `DATA_DIR` for a local run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# run locally with data persisted in ./data
$env:DATA_DIR = (Resolve-Path .\data).Path
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
2. Or serve only static files to verify UI:
```bash
python -m http.server --directory public 8000
# then open http://localhost:8000
```

Testing contact form and inbox
- Submit the contact form from the frontend (on the Railway URL or your local server).
- Check inbox at `/inbox` on the backend URL and sign in with the password (the repo ships a build-time hash; change it from the inbox UI to something you control).

Optional improvements (suggested)
- Run multiple workers using Gunicorn + Uvicorn workers for better concurrency in production.
- Add HTTPS custom domain on Railway or use Vercel's domain for frontend.
- Add logging and alerting (Railway Metrics tab) to monitor errors and traffic.

If you want, I can:
- Walk you step-by-step through Railway settings (I will list exactly which buttons to click), or
- Patch `public/app.js` now to point to your Railway URL once you share it, or
- Create a simple `vercel.json` rewrite that proxies `/api/*` to the Railway backend (advanced; requires Vercel Pro for pattern rewrites).

Let me know which of those you'd like me to do next.
