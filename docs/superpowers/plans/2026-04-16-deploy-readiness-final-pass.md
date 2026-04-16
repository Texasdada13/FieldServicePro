# Deploy-Readiness Final Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 5 surgical in-place edits to the existing FieldServicePro Flask app so it can be safely pointed at a public portfolio URL on Render.

**Architecture:** No new packages, no new modules, no refactors. Each task touches one or two existing files (or adds one tiny new file alongside an existing one) and is independently revertable.

**Tech Stack:** Python 3.11, Flask 3.x, gunicorn, SQLAlchemy 2.x, Flask-Talisman, Flask-Login. Deployed via Render Blueprint (paid Starter plan).

**Spec:** `docs/superpowers/specs/2026-04-16-deploy-readiness-final-pass-design.md`

**Verification approach:** Per the spec, no new automated tests are written (out of scope). Each task is verified by (a) Python AST/compile-check of the changed file, (b) a smoke import of `web.app` to confirm the app boots, and (c) for runtime behavior, a documented manual check at the end of the plan.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `web/auth.py` | Modify (around line 209) | Gate `/demo?reset=1` behind `DEMO_RESET_TOKEN` env var |
| `web/app.py` | Modify (3 spots: lines ~100, ~103, ~745) | (a) Fail-fast on missing `SECRET_KEY` in prod, (b) defensively pin DEBUG/PROPAGATE/TRAP off in prod, (c) add `500` errorhandler + `/robots.txt` route |
| `web/templates/errors/500.html` | Create | Branded 500 page matching `errors/403.html` style |
| `web/static/robots.txt` | Create | Static file with `Disallow: /` |
| `render.yaml` | Modify | Add `DEMO_RESET_TOKEN` env entry (`sync: false`) |

5 files total: 3 modified, 2 created. Zero new dependencies.

---

## Task 1: Fail-fast on missing `SECRET_KEY` in production

**Files:**
- Modify: `web/app.py:103`

- [ ] **Step 1: Read the current `SECRET_KEY` line and surrounding context**

Read `web/app.py` lines 99–107 to confirm the current state matches what the plan expects. Expected current content of line 100–106:

```python
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fsp-dev-secret-key-change-in-prod')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
```

If the file has already been edited away from this state, stop and surface the difference rather than blindly applying the edit.

- [ ] **Step 2: Replace the silent fallback with a fail-fast guard**

Use the Edit tool to replace this exact line in `web/app.py`:

```python
app.secret_key = os.environ.get('SECRET_KEY', 'fsp-dev-secret-key-change-in-prod')
```

with:

```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var is required in production. "
        "Set it in the Render dashboard before deploying."
    )
app.secret_key = SECRET_KEY or 'fsp-dev-secret-key-change-in-prod'
```

- [ ] **Step 3: AST-check the file**

Run:
```bash
python -c "import ast; ast.parse(open('web/app.py').read()); print('AST OK')"
```
Expected output: `AST OK`

- [ ] **Step 4: Smoke-import the app in dev mode (FLASK_ENV unset)**

Run from the repo root:
```bash
python -c "import os, sys; sys.path.insert(0, '.'); os.environ.pop('FLASK_ENV', None); os.environ.pop('SECRET_KEY', None); import web.app; print('dev boot OK, secret_key set:', bool(web.app.app.secret_key))"
```
Expected output: ends with `dev boot OK, secret_key set: True` (no RuntimeError).

- [ ] **Step 5: Smoke-test that production mode without SECRET_KEY now FAILS**

Run:
```bash
python -c "import os, sys; sys.path.insert(0, '.'); os.environ['FLASK_ENV']='production'; os.environ.pop('SECRET_KEY', None); import web.app" 2>&1 | tail -5
```
Expected output: ends with `RuntimeError: SECRET_KEY env var is required in production. ...`

- [ ] **Step 6: Commit**

```bash
git add web/app.py
git commit -m "Fail-fast on missing SECRET_KEY in production

Previously the app silently fell back to a publicly-known dev key when
SECRET_KEY was unset, which would run prod with forgeable session
cookies. Now production refuses to boot without an explicit SECRET_KEY.
Local development behavior is unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Defensively pin debug-off in production

**Files:**
- Modify: `web/app.py` (right after the `SECRET_KEY` block from Task 1)

- [ ] **Step 1: Locate insertion point**

After Task 1, the file should contain (around lines 100–112):

```python
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var is required in production. "
        "Set it in the Render dashboard before deploying."
    )
app.secret_key = SECRET_KEY or 'fsp-dev-secret-key-change-in-prod'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
```

The new block goes immediately after `SESSION_COOKIE_SECURE`.

- [ ] **Step 2: Insert the production debug-off guard**

Use the Edit tool to replace:

```python
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

# File upload config
```

with:

```python
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

# Belt-and-suspenders: never expose the Werkzeug debugger in production,
# even if a stray FLASK_DEBUG env var or future code change tries to enable it.
if IS_PRODUCTION:
    app.config['DEBUG'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.config['TRAP_HTTP_EXCEPTIONS'] = False

# File upload config
```

- [ ] **Step 3: AST-check the file**

Run:
```bash
python -c "import ast; ast.parse(open('web/app.py').read()); print('AST OK')"
```
Expected output: `AST OK`

- [ ] **Step 4: Smoke-import in production mode (with SECRET_KEY set)**

Run:
```bash
python -c "import os, sys; sys.path.insert(0, '.'); os.environ['FLASK_ENV']='production'; os.environ['SECRET_KEY']='test'; import web.app; a=web.app.app; print('debug:', a.config['DEBUG'], 'propagate:', a.config['PROPAGATE_EXCEPTIONS'], 'trap:', a.config['TRAP_HTTP_EXCEPTIONS'])"
```
Expected output: ends with `debug: False propagate: False trap: False`.

- [ ] **Step 5: Commit**

```bash
git add web/app.py
git commit -m "Defensively pin DEBUG/PROPAGATE/TRAP off in production

Belt-and-suspenders against a stray FLASK_DEBUG=1 or future code change
accidentally re-exposing the Werkzeug interactive debugger (which is a
remote-code-execution surface).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Lock down `/demo?reset=1` behind a token

**Files:**
- Modify: `web/auth.py:219` (the `if demo_user and request.args.get('reset') != '1':` line)
- Modify: `render.yaml` (add `DEMO_RESET_TOKEN` env entry)

- [ ] **Step 1: Confirm current `web/auth.py` reset logic**

Read `web/auth.py` lines 215–225. Expected current content:

```python
    db = get_session()
    try:
        # Check if demo account already exists — reset on ?reset=1
        demo_user = db.query(User).filter_by(email='demo@fieldservicepro.app').first()
        if demo_user and request.args.get('reset') != '1':
            login_user(demo_user)
            flash('Welcome back to the demo!', 'success')
            return redirect(url_for('dashboard'))
        elif demo_user:
            # Wipe old demo org cascade
            org_id = demo_user.organization_id
```

The conditional that decides "log in vs wipe-and-re-seed" is line 219 (`if demo_user and request.args.get('reset') != '1':`).

- [ ] **Step 2: Verify `os` is already imported in `web/auth.py`**

Run:
```bash
python -c "import re; src = open('web/auth.py').read(); print('os imported:', bool(re.search(r'^import os|^from os', src, re.M)))"
```
Expected: `os imported: True`. If `False`, the next step also adds `import os` at the top of the file alongside the other stdlib imports.

If `os imported: False`, edit the top of `web/auth.py`:
```python
"""Authentication routes."""

import secrets
```
becomes:
```python
"""Authentication routes."""

import os
import secrets
```

- [ ] **Step 3: Edit the reset gate to require the token**

Use the Edit tool to replace this exact block in `web/auth.py`:

```python
        # Check if demo account already exists — reset on ?reset=1
        demo_user = db.query(User).filter_by(email='demo@fieldservicepro.app').first()
        if demo_user and request.args.get('reset') != '1':
            login_user(demo_user)
            flash('Welcome back to the demo!', 'success')
            return redirect(url_for('dashboard'))
        elif demo_user:
```

with:

```python
        # Check if demo account already exists — reset on ?reset=1&token=<DEMO_RESET_TOKEN>
        demo_user = db.query(User).filter_by(email='demo@fieldservicepro.app').first()
        # Reset is only honored when the caller supplies the operator-only token.
        # Without a valid token, fall through to the "log in to existing demo" path.
        expected_token = os.environ.get('DEMO_RESET_TOKEN')
        provided_token = request.args.get('token')
        reset_requested = request.args.get('reset') == '1'
        reset_authorized = bool(expected_token) and provided_token == expected_token
        if demo_user and not (reset_requested and reset_authorized):
            login_user(demo_user)
            flash('Welcome back to the demo!', 'success')
            return redirect(url_for('dashboard'))
        elif demo_user:
```

- [ ] **Step 4: AST-check `web/auth.py`**

Run:
```bash
python -c "import ast; ast.parse(open('web/auth.py').read()); print('AST OK')"
```
Expected: `AST OK`

- [ ] **Step 5: Add `DEMO_RESET_TOKEN` to `render.yaml`**

Use the Edit tool on `render.yaml` to replace:

```yaml
      # Anthropic API key — required for AI chat panel; leave unset to disable.
      - key: ANTHROPIC_API_KEY
        sync: false
```

with:

```yaml
      # Anthropic API key — required for AI chat panel; leave unset to disable.
      - key: ANTHROPIC_API_KEY
        sync: false

      # Operator-only token to authorize wiping & re-seeding the demo org via
      # GET /demo?reset=1&token=<value>. Without this set, /demo?reset=1 is a no-op.
      - key: DEMO_RESET_TOKEN
        sync: false
```

- [ ] **Step 6: Validate `render.yaml` parses as YAML**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('render.yaml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 7: Smoke-test `web/auth.py` import path still loads cleanly**

Run:
```bash
python -c "import os, sys; sys.path.insert(0, '.'); os.environ['SECRET_KEY']='test'; from web.auth import demo; print('demo route imports OK:', callable(demo))"
```
Expected: ends with `demo route imports OK: True`.

- [ ] **Step 8: Commit**

```bash
git add web/auth.py render.yaml
git commit -m "Gate /demo?reset=1 behind DEMO_RESET_TOKEN env var

Previously any unauthenticated visitor could hit /demo?reset=1 and wipe
the demo organization. Now the reset path only runs when both reset=1
AND token=<DEMO_RESET_TOKEN> are supplied; otherwise it falls through
to the normal 'log in as demo user' path. New env var DEMO_RESET_TOKEN
added to render.yaml as sync:false (operator sets in dashboard).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Custom `500` error handler + `errors/500.html` template

**Files:**
- Create: `web/templates/errors/500.html`
- Modify: `web/app.py` (after the existing `404` handler, around line 745)

- [ ] **Step 1: Create the 500 template**

Write a new file at `web/templates/errors/500.html` with this exact content (mirrors the `errors/403.html` style, swaps the icon, color, and copy):

```html
{% extends "base.html" %}
{% block title %}Something went wrong{% endblock %}
{% block page_title %}Server Error{% endblock %}

{% block content %}
<div class="empty-state" style="padding: var(--space-12) var(--space-6);">
  <i class="bi bi-exclamation-octagon" style="display: block; font-size: 3rem; color: var(--color-danger); margin-bottom: var(--space-4);"></i>
  <h3 style="font-size: var(--font-size-xl);">Something went wrong</h3>
  <p>An unexpected error occurred. The team has been notified — please try again in a moment.</p>
  <a href="{{ url_for('dashboard') }}" class="btn btn-accent">
    <i class="bi bi-house"></i> Go to Dashboard
  </a>
</div>
{% endblock %}
```

- [ ] **Step 2: Add the `500` handler in `web/app.py`**

After Task 3, locate the existing `404` handler in `web/app.py` (around line 740). Use the Edit tool to replace:

```python
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    flash('Page not found.', 'warning')
    return redirect(url_for('dashboard'))
```

with:

```python
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    flash('Page not found.', 'warning')
    return redirect(url_for('dashboard'))


@app.errorhandler(500)
def server_error(e):
    """Branded 500 page. Logs full stack trace to stdout for Render log search."""
    logger.exception("Internal server error: %s", e)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html',
                           active_page='', user=current_user,
                           divisions=[]), 500
```

- [ ] **Step 3: AST-check the file**

Run:
```bash
python -c "import ast; ast.parse(open('web/app.py').read()); print('AST OK')"
```
Expected: `AST OK`

- [ ] **Step 4: Smoke-import and confirm the 500 handler is registered**

Run:
```bash
python -c "
import os, sys
sys.path.insert(0, '.')
os.environ['SECRET_KEY']='test'
import web.app
handlers = web.app.app.error_handler_spec.get(None, {})
print('500 handler registered:', 500 in handlers)
print('404 handler registered:', 404 in handlers)
print('403 handler registered:', 403 in handlers)
"
```
Expected: all three `True`.

- [ ] **Step 5: Commit**

```bash
git add web/app.py web/templates/errors/500.html
git commit -m "Add branded 500 error handler + template

Previously unhandled exceptions rendered Flask's default ugly page on a
public portfolio URL. Now /api/* routes return a JSON 500 and HTML
routes render a branded errors/500.html (matching the existing
errors/403.html style). The handler also calls logger.exception so the
full stack trace lands in Render's stdout log search.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `robots.txt` static file + top-level `/robots.txt` route

**Files:**
- Create: `web/static/robots.txt`
- Modify: `web/app.py` (add a thin route — placement: near the `/health` route, around line 715)

- [ ] **Step 1: Create the static robots file**

Write a new file at `web/static/robots.txt` with this exact content (no trailing blank lines, two lines total):

```
User-agent: *
Disallow: /
```

- [ ] **Step 2: Verify `send_from_directory` is not yet imported in `web/app.py`**

Run:
```bash
python -c "import re; src = open('web/app.py').read(); m = re.search(r'^from flask import .*$', src, re.M); print(m.group(0) if m else 'MISSING')"
```
Expected output: a `from flask import ...` line. Note whether `send_from_directory` is in it.

- [ ] **Step 3: Add `send_from_directory` to the flask import**

If `send_from_directory` is NOT in the existing flask import line, use the Edit tool to replace:

```python
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context, session, g, abort
```

with:

```python
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context, session, g, abort, send_from_directory
```

(If it's already present, skip this step.)

- [ ] **Step 4: Add the `/robots.txt` route**

Locate the existing `/health` route in `web/app.py` (currently at `@app.route('/health')`, around line 715). Use the Edit tool to replace:

```python
# ========== HEALTH CHECK (Render uses this) ==========

@app.route('/health')
def health_check():
```

with:

```python
# ========== HEALTH CHECK (Render uses this) ==========

@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt at the conventional top-level URL."""
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')


@app.route('/health')
def health_check():
```

- [ ] **Step 5: AST-check the file**

Run:
```bash
python -c "import ast; ast.parse(open('web/app.py').read()); print('AST OK')"
```
Expected: `AST OK`

- [ ] **Step 6: Smoke-test the robots route via Flask's test client**

Run:
```bash
python -c "
import os, sys
sys.path.insert(0, '.')
os.environ['SECRET_KEY']='test'
os.environ.pop('FLASK_ENV', None)
import web.app
client = web.app.app.test_client()
r = client.get('/robots.txt')
print('status:', r.status_code)
print('content-type:', r.headers.get('Content-Type'))
print('body:', r.data.decode().strip())
"
```
Expected output:
```
status: 200
content-type: text/plain; charset=utf-8
body: User-agent: *
Disallow: /
```

- [ ] **Step 7: Commit**

```bash
git add web/app.py web/static/robots.txt
git commit -m "Add robots.txt with Disallow:/ and a top-level /robots.txt route

The demo is auth-walled with no marketing content — noindex everything
to keep throwaway demo URLs out of search results. Crawlers only check
/robots.txt (never /static/robots.txt), so a top-level route is required
in addition to the static file.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Final integration smoke test

**Files:** none modified.

- [ ] **Step 1: Verify `web/app.py` still parses and the app boots cleanly in dev mode**

Run from the repo root:
```bash
python -c "
import os, sys
sys.path.insert(0, '.')
os.environ.pop('FLASK_ENV', None)
os.environ.pop('SECRET_KEY', None)
import web.app
a = web.app.app
print('blueprints:', len(a.blueprints))
print('500 handler:', 500 in a.error_handler_spec.get(None, {}))
print('robots route:', '/robots.txt' in [r.rule for r in a.url_map.iter_rules()])
print('demo route:', '/demo' in [r.rule for r in a.url_map.iter_rules()])
print('health route:', '/health' in [r.rule for r in a.url_map.iter_rules()])
"
```
Expected: every line ends with `True` or a count > 50 for blueprints.

- [ ] **Step 2: Verify `web/app.py` still boots cleanly in production mode**

Run:
```bash
python -c "
import os, sys
sys.path.insert(0, '.')
os.environ['FLASK_ENV']='production'
os.environ['SECRET_KEY']='smoke-test-key'
import web.app
a = web.app.app
print('production OK')
print('debug:', a.config['DEBUG'])
print('propagate:', a.config['PROPAGATE_EXCEPTIONS'])
print('trap:', a.config['TRAP_HTTP_EXCEPTIONS'])
"
```
Expected: ends with `debug: False`, `propagate: False`, `trap: False`.

- [ ] **Step 3: Verify `render.yaml` still parses**

Run:
```bash
python -c "import yaml; cfg = yaml.safe_load(open('render.yaml')); env_keys = [e['key'] for e in cfg['services'][0]['envVars']]; print('DEMO_RESET_TOKEN present:', 'DEMO_RESET_TOKEN' in env_keys)"
```
Expected: `DEMO_RESET_TOKEN present: True`

- [ ] **Step 4: Confirm working tree is clean and commits are linear**

Run:
```bash
git status --short && echo "---" && git log --oneline -7
```
Expected:
- `git status --short`: empty (no uncommitted changes)
- `git log --oneline -7`: shows 5 new commits in order — Task 1 (SECRET_KEY), Task 2 (DEBUG pin), Task 3 (demo reset), Task 4 (500 handler), Task 5 (robots) — on top of the spec self-review commit.

- [ ] **Step 5: Print the post-deploy manual verification checklist**

This is the verification the operator (you) must run **after** the next Render deploy completes. It is NOT runnable from this plan because it requires the live URL.

```
Post-deploy manual checks (run against the live Render URL):

1. GET https://<app>.onrender.com/robots.txt
   → Expect 200, Content-Type: text/plain, body "User-agent: *\nDisallow: /"

2. GET https://<app>.onrender.com/demo?reset=1
   → Expect to be logged in as demo user, demo data NOT wiped.

3. GET https://<app>.onrender.com/demo?reset=1&token=wrong
   → Expect to be logged in as demo user, demo data NOT wiped.

4. GET https://<app>.onrender.com/demo?reset=1&token=<value of DEMO_RESET_TOKEN>
   → Expect demo data wiped + re-seeded, then logged in as demo user.

5. Trigger an unhandled exception in any internal route (any URL whose handler
   raises). Expect: branded 500 page rendered, no Werkzeug debugger, no stack
   trace in response body. Render dashboard logs show the stack trace.

6. Trigger an unhandled exception under /api/* (e.g. POST malformed JSON to a
   known API endpoint). Expect: JSON {"error": "Internal server error"} with
   HTTP 500.

7. In Render dashboard, temporarily delete SECRET_KEY env var and redeploy.
   Expect: deploy fails, build/runtime logs show
       RuntimeError: SECRET_KEY env var is required in production.
   Restore SECRET_KEY and redeploy.

8. GET https://<app>.onrender.com/health
   → Expect 200, body {"status":"healthy","database":"connected"}.
```

- [ ] **Step 6: No commit needed for this task**

This task is verification only; no source files change.

---

## Hand-off

This plan ends here. The next step is to invoke `superpowers:executing-plans` to execute Tasks 1–6 in order.

The user has already requested that we chain directly into `superpowers:executing-plans` after this plan is written, so on completion of this writing-plans hand-off, the orchestrator should proceed automatically.
