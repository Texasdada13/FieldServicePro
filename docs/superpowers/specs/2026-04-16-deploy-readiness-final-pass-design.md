# Deploy-Readiness Final Pass — Design Spec

**Date:** 2026-04-16
**Status:** Approved
**Owner:** aasha
**Target environment:** Render (paid Starter plan, separately-provisioned paid PostgreSQL, persistent disk for uploads)
**Use case:** public portfolio / sales-demo URL — anyone on the internet may visit

---

## 1. Goal

Make the existing FieldServicePro app safe to point a public portfolio link at, with no embarrassing failure modes for prospects/recruiters.

**Explicitly NOT a goal:** building new features, refactoring existing code, adding new packages, or hardening the app for real multi-tenant SaaS traffic. Those are deferred.

---

## 2. Context & inputs

| Input | Decision |
|---|---|
| User profile | Demo / portfolio / sales-tool — no real customer data |
| Distribution | Public link in portfolio / LinkedIn — anyone on the internet can visit |
| Demo UX | Per-visitor sandbox model **deferred** (out of scope this pass) |
| Registration policy | Open registration **deferred** abuse hardening (out of scope this pass) |
| External services | Render-only — no Sentry / SaaS dependencies |
| Timeline & discipline | Phased; this spec is Phase 1 only — surgical fixes only, no new modules |
| Sacred files / off-limits | None |

---

## 3. Already shipped (verified, no further action)

These changes were made in the brainstorming session preceding this spec and are committed-or-staged:

1. `python-dateutil>=2.8.0` and `flask-mail>=0.9.1` added to `requirements.txt`
2. `abort` added to the `flask` import in `web/app.py:8` (was used in 13 places without being imported)
3. `models/database.py` `init_db()` imports aligned to include `restock_request`, `feedback_survey`, `tech_performance`
4. `render.yaml` rewritten: paid Starter plan, branch=master, persistent disk `fsp-uploads` (10 GB at `/var/data/uploads`), `UPLOAD_FOLDER` env wired to it, gunicorn access/error logs, no auto-DB (external DB only), placeholder env entries for `DATABASE_URL` / `ANTHROPIC_API_KEY` / `MAIL_*`
5. `DEPLOY.md` rewritten for paid web + manual external DB workflow

---

## 4. In-scope changes (5 surgical edits)

### 4.1 — Lock down `/demo?reset=1`

**File:** `web/auth.py` (the `demo()` route, currently at line 209)

**Problem:** The current implementation lets *any unauthenticated visitor* hit `/demo?reset=1` and wipe + re-seed the demo organization. A bored visitor or scraper can erase the demo seconds before a prospect arrives.

**Change:** Gate the reset path with a token check.

- The `?reset=1` branch only runs when `request.args.get('token') == os.environ.get('DEMO_RESET_TOKEN')`.
- If no `DEMO_RESET_TOKEN` env var is set OR the token doesn't match, ignore the `reset` parameter and fall through to the normal "log in to existing demo user" flow.
- Add `DEMO_RESET_TOKEN` to `render.yaml` as `sync: false` (operator sets the value in Render dashboard).

**Acceptance:**
- `GET /demo` (no params) → logs in as the demo user, no wipe.
- `GET /demo?reset=1` → does NOT wipe; logs in as the demo user.
- `GET /demo?reset=1&token=wrong` → does NOT wipe; logs in as the demo user.
- `GET /demo?reset=1&token=<correct>` → wipes and re-seeds as today.

**Diff size:** ~6 lines added, 1 env entry.

### 4.2 — Custom `500` error handler

**File:** `web/app.py` (next to existing `403` and `404` handlers around line 733); new template at `web/templates/errors/500.html` if it does not already exist.

**Problem:** No `@app.errorhandler(500)` exists. Unhandled exceptions render Flask's default page, which looks unprofessional on a portfolio demo and reveals framework details.

**Change:**
- Add `@app.errorhandler(500)` decorated function that:
  - Calls `logger.exception("Internal server error: %s", e)` so the stack trace lands in Render logs.
  - Returns `jsonify({'error': 'Internal server error'}), 500` for `/api/*` paths.
  - Otherwise renders `errors/500.html` with `user=current_user, active_page='', divisions=[]` (matching the `403` handler shape).
- Create `web/templates/errors/500.html` using the same visual style as `errors/403.html` (extend the same base, same overall layout, with a 500-appropriate message and a link back to `/`).

**Acceptance:**
- Forcing an exception inside any internal route returns a styled 500 page, not Flask's default.
- Forcing an exception inside an `/api/*` route returns `{"error":"Internal server error"}` with HTTP 500.
- Render logs show the full stack trace via `logger.exception`.

**Diff size:** ~10 lines in `web/app.py`, 1 new short HTML template (~30 lines if the file doesn't already exist).

### 4.3 — `robots.txt`

**Files:** new file at `web/static/robots.txt`; new route in `web/app.py`.

**Decision:** Noindex everything by default. The demo is auth-walled, there's no marketing content for crawlers, and we don't want Render demo URLs polluting search results.

**Content of `web/static/robots.txt`:**
```
User-agent: *
Disallow: /
```

**Route in `web/app.py`** (crawlers only check `/robots.txt`, never `/static/robots.txt`, so a top-level route is required):

```python
from flask import send_from_directory

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')
```

**Acceptance:**
- `GET /robots.txt` returns the content above with HTTP 200 and `Content-Type: text/plain`.
- `GET /static/robots.txt` also works (Flask's static handler).

**Diff size:** 2-line new file + ~5-line route in `web/app.py`.

### 4.4 — Defensively pin debug-off in production

**File:** `web/app.py` near the existing `IS_PRODUCTION` block (~line 100)

**Problem:** `app.run(debug=True)` is gated to `__main__` (correct), but there's no defense against a stray `FLASK_DEBUG=1` env var, a typo, or a future code change re-enabling propagation.

**Change:** When `IS_PRODUCTION` is true, explicitly set:
- `app.config['DEBUG'] = False`
- `app.config['PROPAGATE_EXCEPTIONS'] = False`
- `app.config['TRAP_HTTP_EXCEPTIONS'] = False`

Belt-and-suspenders against accidentally exposing the Werkzeug interactive debugger (which would be a remote-code-execution surface).

**Acceptance:**
- After deploy, forcing an exception (see 4.2) shows the branded 500 page, NOT a Werkzeug debugger or stack trace in the response body.

**Diff size:** ~3 lines.

### 4.5 — Fail-fast on missing `SECRET_KEY` in production

**File:** `web/app.py:103`

**Problem:** Today the line `app.secret_key = os.environ.get('SECRET_KEY', 'fsp-dev-secret-key-change-in-prod')` silently falls back to a publicly-known dev key if the env var is missing. A misconfigured production deploy runs with forgeable session cookies — the worst kind of silent failure.

**Change:** Replace with:

```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var is required in production. "
        "Set it in the Render dashboard before deploying."
    )
app.secret_key = SECRET_KEY or 'fsp-dev-secret-key-change-in-prod'
```

Local development is unaffected (still falls back); production refuses to boot without an explicit `SECRET_KEY`.

**Acceptance:**
- Locally, with no `SECRET_KEY` set, the app starts as today.
- Locally, with `FLASK_ENV=production` and no `SECRET_KEY`, app boot raises `RuntimeError`.
- On Render, `SECRET_KEY` is auto-generated by `render.yaml`'s `generateValue: true`, so this should never fire — but if someone deletes it from the dashboard, the next deploy fails loud.

**Diff size:** ~5 lines (replacing 1 line).

---

## 5. Verification — manual smoke checks post-deploy

Run these against the live Render URL after the first deploy following these changes:

1. `GET /robots.txt` → returns `User-agent: *\nDisallow: /`
2. `GET /demo?reset=1` (no token) → logs in as demo user; demo data unchanged.
3. `GET /demo?reset=1&token=wrong` → logs in as demo user; demo data unchanged.
4. `GET /demo?reset=1&token=<value of DEMO_RESET_TOKEN>` → demo data is wiped and re-seeded, then logged in.
5. Trigger an exception in any internal route (e.g. craft a request that hits a known crash path) → response is the new branded 500 page, no Werkzeug debugger, no stack trace in the response body. Render logs show the stack trace via `logger.exception`.
6. Trigger an exception in any `/api/*` route → response is `{"error":"Internal server error"}` with HTTP 500.
7. In Render dashboard: temporarily delete `SECRET_KEY` env var and redeploy → service refuses to boot, log shows `RuntimeError: SECRET_KEY env var is required in production.` Then restore the env var and redeploy.
8. `GET /health` → unchanged: `{"status":"healthy","database":"connected"}` with HTTP 200.

---

## 6. Out of scope (explicitly deferred)

The following are real production-readiness gaps but are **not** addressed in this pass, per the user's directive to make minimal surgical changes only:

- Multi-tenant authorization audit (236 `filter_by(id=…)` lookups not scoped to `organization_id`)
- Replacing 90 silent `except Exception: pass` swallowed errors with proper logging
- Rate limiting on `/auth/login`, `/auth/register`, `/demo`, booking form
- CSRF protection on internal POST forms (Flask-WTF)
- Per-visitor sandbox demo model
- External error tracking (Sentry / Rollbar)
- Structured (JSON) logging
- Alembic baseline migration
- GitHub Actions CI
- Test coverage for critical paths

These should each be brainstormed as their own spec when there's appetite to address them.

---

## 7. Rollback

Each of the 5 edits is an isolated commit-sized change with no DB migration and no data dependency. Any single item can be reverted with `git revert <commit-sha>` without affecting the others. The `DEMO_RESET_TOKEN` env var, if added and later removed, simply means `/demo?reset=1` becomes a no-op (which is the safe default).

---

## 8. Files touched (final list)

- `web/auth.py` — edit (gate reset behind token)
- `web/app.py` — edit in 3 spots (SECRET_KEY guard, debug pinning, 500 handler) + optional `/robots.txt` thin route
- `web/templates/errors/500.html` — new file (or edit if it exists)
- `web/static/robots.txt` — new file
- `render.yaml` — add `DEMO_RESET_TOKEN` env entry (`sync: false`)

**Totals:** 3 edits, 2 new files, 1 env var addition, 0 new dependencies, 0 new packages.

---

## 9. Next steps

1. User reviews this spec.
2. On approval, hand off to `superpowers:writing-plans` to convert this design into a step-by-step implementation plan with checkpoints.
3. Plan hands off to `superpowers:executing-plans` to perform the edits with verification at each step.
