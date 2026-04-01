# Deploying FieldServicePro to Render

## Prerequisites

- GitHub repository connected to Render
- Branch to deploy: `master`

---

## Option A: Blueprint Deploy (Recommended)

The `render.yaml` file auto-configures everything.

1. Go to **Render Dashboard** > **New** > **Blueprint**
2. Connect your GitHub repo and select the `master` branch
3. Render will auto-detect `render.yaml` and create:
   - **Web Service**: `fieldservicepro`
   - **PostgreSQL Database**: `fieldservicepro-db` (free plan)
4. The following env vars are auto-configured:
   - `DATABASE_URL` — linked from the PostgreSQL instance
   - `SECRET_KEY` — auto-generated secure value
   - `FLASK_ENV` — set to `production`
   - `PYTHON_VERSION` — `3.11.4`
5. **Manually add** (Render Dashboard > Environment):
   - `ANTHROPIC_API_KEY` — your Anthropic API key (only if you want AI chat)
6. Click **Apply** to deploy

---

## Option B: Manual Setup

### 1. Create PostgreSQL Database

- Render Dashboard > **New** > **PostgreSQL**
- Name: `fieldservicepro-db`
- Database: `fieldservicepro`
- User: `fsp_admin`
- Plan: Free
- Copy the **Internal Connection String**

### 2. Create Web Service

- Render Dashboard > **New** > **Web Service**
- Connect GitHub repo, branch `master`
- Runtime: **Python**
- Build Command: `./build.sh`
- Start Command: `gunicorn web.app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- Health Check Path: `/health`

### 3. Set Environment Variables

| Variable | Value |
|---|---|
| `DATABASE_URL` | (paste Internal Connection String from step 1) |
| `SECRET_KEY` | (generate a random string: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `FLASK_ENV` | `production` |
| `PYTHON_VERSION` | `3.11.4` |
| `ANTHROPIC_API_KEY` | (optional — your Anthropic key for AI chat) |

---

## Post-Deployment Checklist

1. **Check deploy logs** — look for `gunicorn` startup message
2. **Test health check** — `GET https://your-app.onrender.com/health` should return `{"status": "healthy", "database": "connected"}`
3. **Test the demo** — visit `/demo` to create a pre-loaded demo account
4. **Test login** — register a new account at `/register`
5. **Test AI chat** — only works if `ANTHROPIC_API_KEY` is set; returns 503 otherwise (graceful)

## Notes

- **Database tables** are auto-created on first startup via SQLAlchemy `create_all()`
- **No migrations needed** — the app uses auto-schema creation
- **Free tier spin-down**: Render free tier spins down after 15 min of inactivity. First request after spin-down takes ~30s
- **SQLite is NOT used in production** — when `DATABASE_URL` is set, the app connects to PostgreSQL
