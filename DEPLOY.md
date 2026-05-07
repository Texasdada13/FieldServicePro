# Deploying 4MAN Services Pro to Render

This setup uses Render's **Blueprint** to provision the web service, persistent
disk, and PostgreSQL database in one step. The DB connection string is
auto-wired into the web service via `fromDatabase`, so no manual paste is
needed.

## Prerequisites

- GitHub repository connected to Render
- Branch to deploy: `4MAN-SERVICES-PRO`
- A Render account with billing enabled (Basic Postgres is a paid plan)

---

## Step 1 — Deploy via Blueprint

1. Render Dashboard → **New** → **Blueprint**
2. Connect the GitHub repo and select the `4MAN-SERVICES-PRO` branch
3. Render auto-detects `render.yaml` and provisions:
   - **Web Service**: `4man-services-pro` (Starter plan)
   - **Persistent Disk**: `4man-uploads` (10 GB at `/var/data/uploads`)
   - **PostgreSQL**: `4man-services-pro-db` (Basic-256MB plan)
4. The following env vars are auto-configured by the blueprint:
   - `PYTHON_VERSION` = `3.11.4`
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` (auto-generated)
   - `UPLOAD_FOLDER` = `/var/data/uploads`
   - `DATABASE_URL` (auto-wired from the Postgres database above)

> Both the web service and database are pinned to `oregon`. If you change one,
> change both — they must share a region for the Internal connection string.

---

## Step 2 — Set the remaining env vars in the Render dashboard

Open the web service → **Environment** tab and set whichever apply:

| Variable | Required? | Value |
|---|---|---|
| `ANTHROPIC_API_KEY` | required for AI chat | Anthropic API key |
| `CLAUDE_MODEL` | optional | Override default Claude model |
| `DEMO_RESET_TOKEN` | optional | Token for `/demo?reset=1&token=…` |
| `MAIL_SERVER` | optional | SMTP host (e.g. `smtp.sendgrid.net`) |
| `MAIL_PORT` | optional | usually `587` |
| `MAIL_USE_TLS` | optional | `true` |
| `MAIL_USERNAME` | optional | SMTP username |
| `MAIL_PASSWORD` | optional | SMTP password |
| `MAIL_DEFAULT_SENDER` | optional | `noreply@yourdomain.com` |

Without `ANTHROPIC_API_KEY` the AI chat returns **503** (graceful — rest of the
app keeps working).
Without `MAIL_*` all emails log to console only (no failure).

Click **Save Changes** — Render will redeploy.

---

## Step 3 — Post-deploy verification

1. **Watch deploy logs** — look for:
   - `==> Build complete.`
   - `Database tables initialized successfully.`
   - `FieldServicePro app initialized (production=True)`
   - `Listening at: http://0.0.0.0:$PORT (gunicorn)`
2. **Health check** — `GET https://your-app.onrender.com/health` →
   `{"status":"healthy","database":"connected"}`
3. **Demo account** — visit `/demo` to auto-create a pre-loaded demo org
4. **Register a real account** at `/auth/register`
5. **Upload a file** (any document) → reload after a few minutes → confirm it
   persists (validates the disk mount)
6. **AI chat** (only if `ANTHROPIC_API_KEY` set) — open the chat panel from
   the dashboard

---

## Notes & Operations

- **Schema**: tables are auto-created on first startup via SQLAlchemy
  `Base.metadata.create_all()` in `init_db()`. No Alembic migrations needed
  for a fresh deploy.
- **Future schema changes**: the `migrate_*.py` scripts in the repo are
  SQLite-only. For production schema changes, either (a) add columns via
  manual `psql` ALTER TABLE, or (b) introduce Alembic.
- **Uploads**: stored on the persistent disk at `/var/data/uploads`. Disk is
  zone-pinned and survives deploys/restarts.
- **Backups**: Render paid Postgres includes daily backups; verify the
  retention policy on your plan.
- **Region affinity**: web service and database are both `oregon`. Update both
  in `render.yaml` if you move regions.
- **Scaling**:
  - Web: bump `plan:` (starter → standard → pro) and raise `--workers`.
    Rule of thumb: `(2 × CPU) + 1` workers.
  - DB: upgrade `plan:` (basic-256mb → basic-1gb → basic-4gb → pro-*) in
    `render.yaml`, or change it directly in the dashboard.
- **Custom domain & TLS**: add it in the dashboard under **Settings → Custom
  Domains**. Talisman in `web/app.py` already enforces HTTPS-redirect and
  HSTS when `FLASK_ENV=production`.
