# 4MAN Services Pro — Visual Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FieldServicePro visual identity with the 4MAN Services Pro brand (navy + gold, classic-industrial feel) across staff-facing surfaces and the client portal, without modifying any functional code.

**Architecture:** Token-driven. Concentrate the rebrand in `web/static/css/variables.css` and let the existing design-token system propagate the change. Build a single reusable `_brand.html` Jinja partial (with `mark`, `sidebar_lockup`, `hero_lockup` macros) so every brand-bearing template references the same source of truth. Leave `auth/base_auth.html` and `portal/auth/login.html` (which currently inline their own styles) refactored to use a new shared cream brand surface. Booking templates are tenant-branded already and stay untouched.

**Tech Stack:** Flask + Jinja2, Bootstrap 5.3.2, custom CSS (variables.css → components.css → style.css cascade), Google Fonts (Inter + new Playfair Display), inline SVG.

**Companion spec:** `docs/superpowers/specs/2026-04-27-4man-rebrand-design.md`

**Important deviation from spec:** During plan-writing I read `web/templates/booking/base.html` and found it already uses `{{ org.name }}` and `{{ org.logo_url }}` — it's tenant-branded for the org's clients, *not* SaaS-branded. Replacing this with the 4MAN lockup would break a deliberate multi-tenancy feature. **Booking is therefore excluded from this rebrand.** Booking will pick up new color tokens automatically via `booking.css` if/where it uses them, but no template-level edits.

---

## File Structure

**Created:**
- `web/templates/partials/_brand.html` — three macros: `mark(size)`, `sidebar_lockup()`, `hero_lockup()`. Single source of truth for the new logo system.
- `web/static/img/4man-logo.svg` — standalone SVG file for places that need a real URL (PDF generation, email clients that strip inline SVG).

**Modified (CSS):**
- `web/static/css/variables.css` — token replacements + new tokens (`--color-cream`, `--font-family-display`, etc.).
- `web/static/css/components.css` — button restyle (gold primary), badge color shifts, active-state gold treatment, new `.brand-surface` utility class.
- `web/static/css/style.css` — new `.auth-split` layout for split-screen auth + hero-lockup styles.

**Modified (templates):**
- `web/templates/base.html` — favicon, fonts link, theme-color, title, page meta.
- `web/templates/partials/sidebar.html` — replace inline brand block with `{% from 'partials/_brand.html' import sidebar_lockup %}`.
- `web/templates/auth/base_auth.html` — full rewrite as cream-surface split-screen layout that consumes the global stylesheet (instead of its 80+ lines of inline styles).
- `web/templates/auth/login.html` — title string + `auth-subtitle` text.
- `web/templates/auth/register.html` — title string only.
- `web/templates/portal/base.html` — title string + brand block.
- `web/templates/portal/auth/login.html` — full rewrite as cream-surface split-screen.
- `web/templates/portal/email/base_email.html` — navy header + Playfair brand title; footer copy.
- `web/templates/errors/403.html` — page-title text only (cream-surface treatment auto-inherits via base.html's new tokens).
- `web/templates/errors/500.html` — page-title text only.

**NOT modified (intentionally):**
- `web/templates/booking/base.html` — tenant-branded, see deviation above.
- `web/static/css/portal.css` — portal cards have their own `--portal-*` token namespace; they pick up the navy/gold via *manual* token updates only on auth pages, not the inner portal. (Inner portal stays on its existing blue palette since it's a client-facing surface; rebranding it is a separate decision.)
- Any `*.py`, `*.js`, `requirements.txt`, `render.yaml`, models, routes, migrations.

---

## Task 1: Variables.css — token swap + new brand tokens

**Files:**
- Modify: `web/static/css/variables.css`

- [ ] **Step 1: Replace the brand color block**

In `web/static/css/variables.css`, replace lines 7-26 (the `-- Brand Colors --` and `-- Surfaces --` related tokens) with:

```css
  /* -- Brand Colors -- */
  --color-primary:        #0d1b3d;
  --color-primary-light:  #1e2d5c;
  --color-primary-dark:   #06122b;

  --color-accent:         #e3b53a;
  --color-accent-light:   #f1c95b;
  --color-accent-dark:    #b8902a;

  --color-warning:        #ea580c;
  --color-warning-light:  #fed7aa;
  --color-warning-dark:   #c2410c;

  --color-danger:         #ef4444;
  --color-danger-light:   #fee2e2;
  --color-danger-dark:    #dc2626;

  --color-success:        #10b981;
  --color-success-light:  #d1fae5;
  --color-success-dark:   #059669;
```

Leave `--color-bg`, `--color-surface`, etc. as-is. Then update `--color-text-primary` (line 36) to `#0d1b3d`. Then update `--sidebar-active-bg` (line 50) to `rgba(227,181,58,0.15)`.

- [ ] **Step 2: Add new tokens**

In the same file, after the existing `:root` block (just before the closing `}` on line 109), insert:

```css

  /* -- 4MAN brand surfaces (auth/portal/error pages) -- */
  --color-cream:          #f5ecd7;
  --color-cream-border:   #e6d9b8;
  --color-cream-text:     #0d1b3d;

  /* -- Display typography (brand wordmark only — not for body/UI) -- */
  --font-family-display:  'Playfair Display', Georgia, 'Times New Roman', serif;
```

- [ ] **Step 3: Browser smoke check**

Start the dev server (whatever command you normally use, e.g. `python web/app.py` or `flask run`). Log in (or use demo). Confirm: dashboard loads, sidebar is darker navy, primary buttons are gold with navy text (yes, even before component CSS — many use `background: var(--color-accent)`), text is legible. Some glitches expected at this stage (e.g., button text may still be white-on-gold if hardcoded) — that's fine, we fix in Task 4.

- [ ] **Step 4: Commit**

```bash
git add web/static/css/variables.css
git commit -m "rebrand: swap color tokens to navy/gold + add cream + display font tokens"
```

---

## Task 2: Build the brand partial (`_brand.html`)

**Files:**
- Create: `web/templates/partials/_brand.html`

- [ ] **Step 1: Create the partial with three macros**

Create `web/templates/partials/_brand.html` with this exact content:

```jinja
{# 4MAN Services Pro — brand component
   Three macros: mark(size), sidebar_lockup(), hero_lockup()
   Single source of truth for the logo system.

   USAGE:
     {% from 'partials/_brand.html' import mark, sidebar_lockup, hero_lockup %}
     {{ mark(28) }}
     {{ sidebar_lockup() }}
     {{ hero_lockup() }}
#}

{% macro mark(size=28, on_dark=false) -%}
  {# Gear/sun mark. on_dark=true removes the navy rounded square so the gold gear sits on a dark bg directly. #}
  <svg width="{{ size }}" height="{{ size }}" viewBox="0 0 64 64" fill="none"
       xmlns="http://www.w3.org/2000/svg" aria-hidden="true" class="brand-mark">
    {% if not on_dark %}
    <rect width="64" height="64" rx="9" fill="#0d1b3d"/>
    {% endif %}
    {# 12 trapezoidal rays around the center, gold #e3b53a #}
    <g fill="#e3b53a" transform="translate(32 32)">
      {% for i in range(12) %}
      <rect x="-3.5" y="-26" width="7" height="9" rx="1.5"
            transform="rotate({{ i * 30 }})"/>
      {% endfor %}
    </g>
    {# Center disc with navy bullseye #}
    <circle cx="32" cy="32" r="9" fill="#e3b53a"/>
    <circle cx="32" cy="32" r="3.5" fill="#0d1b3d"/>
  </svg>
{%- endmacro %}

{% macro sidebar_lockup() -%}
  {# Compact lockup for the sidebar — mark + small wordmark, on dark navy bg #}
  <span class="brand-sidebar-lockup">
    {{ mark(28, on_dark=true) }}
    <span class="brand-sidebar-wordmark">
      <span class="brand-sidebar-wordmark__primary">4MAN</span>
      <span class="brand-sidebar-wordmark__secondary">Services Pro</span>
    </span>
  </span>
{%- endmacro %}

{% macro hero_lockup(tagline=true, subhead=none) -%}
  {# Full lockup for login/auth/error pages on cream surface #}
  <div class="brand-hero-lockup">
    <div class="brand-hero-lockup__mark">{{ mark(96) }}</div>
    <div class="brand-hero-lockup__wordmark">
      <div class="brand-hero-lockup__line1">4MAN</div>
      <div class="brand-hero-lockup__rule"></div>
      <div class="brand-hero-lockup__line2">
        <span class="brand-hero-lockup__services">SERVICES</span>
        <span class="brand-hero-lockup__pro">PRO</span>
      </div>
    </div>
    {% if tagline %}
    <div class="brand-hero-lockup__tagline">JOBS &middot; INVOICING &middot; MANAGEMENT</div>
    {% endif %}
    {% if subhead %}
    <div class="brand-hero-lockup__subhead">{{ subhead }}</div>
    {% endif %}
  </div>
{%- endmacro %}
```

- [ ] **Step 2: Create standalone SVG asset file**

Create `web/static/img/4man-logo.svg` with this exact content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" rx="9" fill="#0d1b3d"/>
  <g fill="#e3b53a" transform="translate(32 32)">
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(0)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(30)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(60)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(90)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(120)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(150)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(180)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(210)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(240)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(270)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(300)"/>
    <rect x="-3.5" y="-26" width="7" height="9" rx="1.5" transform="rotate(330)"/>
  </g>
  <circle cx="32" cy="32" r="9" fill="#e3b53a"/>
  <circle cx="32" cy="32" r="3.5" fill="#0d1b3d"/>
</svg>
```

- [ ] **Step 3: Commit**

```bash
git add web/templates/partials/_brand.html web/static/img/4man-logo.svg
git commit -m "rebrand: add reusable 4MAN brand partial + standalone SVG"
```

---

## Task 3: Update `base.html` (app shell)

**Files:**
- Modify: `web/templates/base.html`

- [ ] **Step 1: Replace `<head>` brand metadata**

In `web/templates/base.html`, replace lines 6-11 (the meta tags + favicon) with:

```html
  <meta name="theme-color" content="#0d1b3d">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="4MAN Services Pro">
  <meta name="description" content="4MAN Services Pro — Field service management for jobs, invoicing, and team operations">
  <title>{% block title %}4MAN Services Pro{% endblock %} — 4MAN Services Pro</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='9' fill='%230d1b3d'/><g fill='%23e3b53a' transform='translate(32 32)'><rect x='-3.5' y='-26' width='7' height='9' rx='1.5'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(30)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(60)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(90)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(120)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(150)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(180)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(210)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(240)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(270)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(300)'/><rect x='-3.5' y='-26' width='7' height='9' rx='1.5' transform='rotate(330)'/></g><circle cx='32' cy='32' r='9' fill='%23e3b53a'/><circle cx='32' cy='32' r='3.5' fill='%230d1b3d'/></svg>">
```

- [ ] **Step 2: Add Playfair Display to the Google Fonts link**

In `web/templates/base.html`, replace line 16:

```html
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

with:

```html
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700;800;900&display=swap" rel="stylesheet">
```

- [ ] **Step 3: Browser smoke check**

Reload the dashboard. Check the browser tab — favicon should now be the gold gear on navy. Page title bar should say "Dashboard — 4MAN Services Pro" (or similar). Sidebar still says "FieldServicePro" — we fix in Task 4.

- [ ] **Step 4: Commit**

```bash
git add web/templates/base.html
git commit -m "rebrand: update base.html favicon, theme-color, fonts, brand strings"
```

---

## Task 4: Update sidebar with brand partial + brand styles in components.css

**Files:**
- Modify: `web/templates/partials/sidebar.html`
- Modify: `web/static/css/components.css`

- [ ] **Step 1: Replace the sidebar brand block**

In `web/templates/partials/sidebar.html`, replace lines 1-16 (the entire opening `<nav>` + brand block):

```html
<!-- FieldServicePro — Sidebar Navigation -->
<nav class="sidebar" id="appSidebar" aria-label="Main navigation">

  <!-- Wordmark / Logo -->
  <div class="sidebar__brand">
    <a href="{{ url_for('dashboard') }}" class="sidebar__logo-link">
      <svg class="sidebar__icon-mark" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect width="28" height="28" rx="7" fill="#0d9488"/>
        <path d="M7 10h14M7 14h10M7 18h7" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
        <circle cx="21" cy="18" r="3" fill="#f59e0b"/>
      </svg>
      <span class="sidebar__wordmark">
        <span class="sidebar__wordmark-main">FieldService</span><span class="sidebar__wordmark-accent">Pro</span>
      </span>
    </a>
  </div>
```

with:

```html
<!-- 4MAN Services Pro — Sidebar Navigation -->
{% from 'partials/_brand.html' import sidebar_lockup %}
<nav class="sidebar" id="appSidebar" aria-label="Main navigation">

  <!-- Wordmark / Logo -->
  <div class="sidebar__brand">
    <a href="{{ url_for('dashboard') }}" class="sidebar__logo-link">
      {{ sidebar_lockup() }}
    </a>
  </div>
```

- [ ] **Step 2: Add brand styles to components.css**

Append the following to the end of `web/static/css/components.css`:

```css

/* ========================================
   4MAN BRAND COMPONENTS
   ======================================== */

/* Sidebar lockup */
.brand-sidebar-lockup {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.brand-sidebar-wordmark {
  display: flex;
  flex-direction: column;
  line-height: 1;
}

.brand-sidebar-wordmark__primary {
  font-family: var(--font-family-display);
  font-weight: 800;
  font-size: 1.05rem;
  color: var(--color-accent);
  letter-spacing: 0.04em;
}

.brand-sidebar-wordmark__secondary {
  font-family: var(--font-family);
  font-weight: 500;
  font-size: 0.7rem;
  color: var(--sidebar-text);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 2px;
}

/* Hide secondary line when sidebar is collapsed */
.sidebar.is-collapsed .brand-sidebar-wordmark { display: none; }

/* Hero lockup (auth/error/portal pages) */
.brand-hero-lockup {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: var(--color-primary);
}

.brand-hero-lockup__mark { margin-bottom: var(--space-5); }

.brand-hero-lockup__wordmark {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: var(--font-family-display);
  color: var(--color-primary);
  line-height: 1;
}

.brand-hero-lockup__line1 {
  font-size: 3.5rem;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.brand-hero-lockup__rule {
  width: 70%;
  height: 3px;
  background: var(--color-accent);
  margin: var(--space-3) 0;
}

.brand-hero-lockup__line2 {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.brand-hero-lockup__services {
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.35em;
  padding-right: 0.35em; /* Optical balance for the wide tracking */
}

.brand-hero-lockup__pro {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: var(--color-primary);
  color: var(--color-accent);
  font-family: var(--font-family);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  border-radius: var(--radius-full);
}

.brand-hero-lockup__tagline {
  margin-top: var(--space-5);
  font-family: var(--font-family);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.25em;
  color: var(--color-text-secondary);
}

.brand-hero-lockup__subhead {
  margin-top: var(--space-3);
  font-family: var(--font-family);
  font-size: 0.95rem;
  color: var(--color-text-secondary);
  max-width: 28rem;
}

/* Cream brand surface (auth, errors, portal-login left panel) */
.brand-surface {
  background-color: var(--color-cream);
  color: var(--color-cream-text);
}

.brand-surface a { color: var(--color-primary); }
.brand-surface a:hover { color: var(--color-accent-dark); }
```

- [ ] **Step 3: Update sidebar active-state CSS for gold treatment**

Search `web/static/css/style.css` for the `.sidebar__link.is-active` rule. (Use Grep: `grep -n "sidebar__link" web/static/css/style.css | head -20`.) Find the rule that styles the active link and update its `border-left` (or pseudo-element) to use `var(--color-accent)` instead of any hardcoded teal value. If the active style currently uses `var(--sidebar-active-bg)` and `var(--sidebar-icon-active)`, both already auto-update from Task 1's token swap — verify visually rather than editing.

If you find no hardcoded teal in the active state, no edit is needed in this step.

- [ ] **Step 4: Browser smoke check**

Reload the dashboard. Sidebar header should now show: gold gear ring + "4MAN" in serif gold + "Services Pro" small caps in light grey. Active sidebar item should have a gold tint instead of teal.

- [ ] **Step 5: Commit**

```bash
git add web/templates/partials/sidebar.html web/static/css/components.css
git commit -m "rebrand: sidebar uses 4MAN brand partial; add hero/sidebar lockup styles"
```

---

## Task 5: Component restyles (buttons, badges, links)

**Files:**
- Modify: `web/static/css/components.css`

- [ ] **Step 1: Inspect existing button styles**

In `web/static/css/components.css`, scroll to the `BUTTONS` section (around line 70). Find every place that hardcodes a teal/green value (search the file for `#0d9488`, `#0f766e`, `#14b8a6`). Plan to replace each with the appropriate token (`var(--color-accent)`, etc.). If buttons already reference tokens (`var(--color-accent)`), no replacement is needed there — they auto-update.

- [ ] **Step 2: Set `.btn-primary` (or equivalent) text color to navy**

Find the rule that styles the primary button background. Currently it likely sets `background: var(--color-accent); color: white;`. Update the `color` to `var(--color-primary)` so gold buttons get navy text (high contrast, matches the logo's "PRO" pill):

```css
/* Primary button — gold with navy text */
.btn-primary,
.btn-accent {
  background-color: var(--color-accent);
  color: var(--color-primary);
  border-color: var(--color-accent);
}

.btn-primary:hover,
.btn-accent:hover {
  background-color: var(--color-accent-light);
  border-color: var(--color-accent-light);
  color: var(--color-primary);
}

.btn-primary:active,
.btn-accent:active {
  background-color: var(--color-accent-dark);
  border-color: var(--color-accent-dark);
  color: var(--color-primary);
}
```

If those exact selectors don't exist, search for the actual rule that targets primary/accent buttons and update its `color` to `var(--color-primary)`. If both `.btn-primary` and `.btn-accent` exist with different intent (e.g., one teal, one slate), keep both but make sure neither uses white text on gold.

- [ ] **Step 3: Update body link color**

Search `components.css` and `style.css` for `a {` at the start of a rule. Body anchors should use navy on white surfaces. If the current rule is `a { color: var(--color-accent); }`, change to `a { color: var(--color-primary); }`. Add hover that uses `var(--color-accent-dark)`.

If links are already navy-colored, no edit needed.

- [ ] **Step 4: Update badge color hardcodings**

Search `components.css` for `background: var(--color-accent)` in badge rules. These all inherit from Task 1's token change automatically. Search also for `background: var(--color-warning)` — same. No manual edits expected.

If you find badges with hardcoded `#0d9488`, replace with `var(--color-accent)`.

- [ ] **Step 5: Browser smoke check**

Reload the dashboard. Click "+ New Job" or any primary CTA button. Background should be gold; text should be navy (not white). Hover should brighten the gold. Side links should be navy. Click a sidebar link — gold left-edge accent.

- [ ] **Step 6: Commit**

```bash
git add web/static/css/components.css
git commit -m "rebrand: primary buttons gold-on-navy; link/badge token cleanup"
```

---

## Task 6: Style.css — split-screen auth layout

**Files:**
- Modify: `web/static/css/style.css`

- [ ] **Step 1: Append split-screen auth layout to style.css**

Append the following to the end of `web/static/css/style.css`:

```css

/* ========================================
   AUTH SPLIT-SCREEN LAYOUT
   Used by auth/base_auth.html and portal/auth/login.html
   ======================================== */
.auth-split {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--color-bg);
}

.auth-split__brand {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-12) var(--space-10);
  background-color: var(--color-cream);
  color: var(--color-cream-text);
}

.auth-split__brand-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.auth-split__brand-footer {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  text-align: center;
  letter-spacing: 0.05em;
}

.auth-split__form {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-10);
  background: var(--color-surface);
}

.auth-split__form-card {
  width: 100%;
  max-width: 26rem;
}

.auth-split__title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: var(--space-2);
  font-family: var(--font-family);
}

.auth-split__description {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-6);
}

.auth-split__form-group {
  margin-bottom: var(--space-4);
}

.auth-split__form-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-primary);
  margin-bottom: var(--space-2);
}

.auth-split__form-group input[type="text"],
.auth-split__form-group input[type="email"],
.auth-split__form-group input[type="password"] {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.95rem;
  font-family: var(--font-family);
  color: var(--color-primary);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.auth-split__form-group input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(227,181,58,0.18);
}

.auth-split__form-row {
  display: flex;
  gap: var(--space-4);
}

.auth-split__form-row .auth-split__form-group { flex: 1; }

.auth-split__btn {
  width: 100%;
  padding: 0.875rem 1.5rem;
  background-color: var(--color-accent);
  color: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: background-color var(--transition-fast), transform var(--transition-fast);
  font-family: var(--font-family);
}

.auth-split__btn:hover {
  background-color: var(--color-accent-light);
  transform: translateY(-1px);
}

.auth-split__btn--secondary {
  background-color: transparent;
  color: var(--color-primary);
  border: 1.5px solid var(--color-primary);
  margin-top: var(--space-3);
}

.auth-split__btn--secondary:hover {
  background-color: var(--color-primary);
  color: var(--color-cream);
  transform: translateY(-1px);
}

.auth-split__links {
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
  text-align: center;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.auth-split__links a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.auth-split__links a:hover {
  text-decoration: underline;
  color: var(--color-accent-dark);
}

.auth-split__flash {
  margin-bottom: var(--space-4);
}

.auth-split__flash .flash {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  margin-bottom: var(--space-2);
  border-left: 4px solid;
}

.auth-split__flash .flash-error,
.auth-split__flash .flash-danger {
  background: var(--color-danger-light);
  color: var(--color-danger-dark);
  border-color: var(--color-danger);
}

.auth-split__flash .flash-success {
  background: var(--color-success-light);
  color: var(--color-success-dark);
  border-color: var(--color-success);
}

.auth-split__flash .flash-info {
  background: rgba(13,27,61,0.06);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.auth-split__flash .flash-warning {
  background: var(--color-warning-light);
  color: var(--color-warning-dark);
  border-color: var(--color-warning);
}

/* Mobile collapse */
@media (max-width: 768px) {
  .auth-split { grid-template-columns: 1fr; min-height: 100vh; }
  .auth-split__brand {
    padding: var(--space-8) var(--space-5);
    min-height: auto;
  }
  .auth-split__brand-inner .brand-hero-lockup__line1 { font-size: 2.5rem; }
  .auth-split__form { padding: var(--space-8) var(--space-5); }
}

/* Password strength bar (used by register page) */
.auth-split__password-strength {
  margin-top: 0.4rem;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.auth-split__password-strength-bar {
  height: 100%;
  transition: width 0.3s, background-color 0.3s;
}

.strength-weak   { width: 33%; background: var(--color-danger); }
.strength-medium { width: 66%; background: var(--color-warning); }
.strength-strong { width: 100%; background: var(--color-success); }
```

- [ ] **Step 2: Commit**

```bash
git add web/static/css/style.css
git commit -m "rebrand: add split-screen auth layout styles"
```

---

## Task 7: Auth pages — full rewrite using split-screen

**Files:**
- Modify: `web/templates/auth/base_auth.html`
- Modify: `web/templates/auth/login.html`
- Modify: `web/templates/auth/register.html`

- [ ] **Step 1: Rewrite `auth/base_auth.html`**

Replace the entire contents of `web/templates/auth/base_auth.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0d1b3d">
    <title>{% block title %}4MAN Services Pro{% endblock %}</title>
    <link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='img/4man-logo.svg') }}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/variables.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body style="font-family: var(--font-family);">
{% from 'partials/_brand.html' import hero_lockup %}
<div class="auth-split">

    <aside class="auth-split__brand">
        <div></div>
        <div class="auth-split__brand-inner">
            {{ hero_lockup(tagline=true, subhead="Field service management built for modern operations") }}
        </div>
        <div class="auth-split__brand-footer">
            &copy; {{ now.year if now else 2026 }} 4MAN Services Pro &middot; All rights reserved
        </div>
    </aside>

    <main class="auth-split__form">
        <div class="auth-split__form-card">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    <div class="auth-split__flash">
                        {% for category, message in messages %}
                            <div class="flash flash-{{ category }}">{{ message }}</div>
                        {% endfor %}
                    </div>
                {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
    </main>

</div>
</body>
</html>
```

Note: this template no longer has inline `<style>` block. All styles come from the global stylesheets. The `.auth-card`, `.auth-header`, `.auth-logo`, `.auth-title`, `.auth-description`, `.form-group`, `.form-row`, `.btn`, `.btn-primary`, `.auth-links`, `.password-strength`, `.checkbox-group`, `.terms-text` classes used by `login.html` and `register.html` need new equivalents in our `auth-split__*` namespace. Step 2 updates those templates.

- [ ] **Step 2: Update `auth/login.html` to use new class names + brand strings**

Replace the entire contents of `web/templates/auth/login.html` with:

```html
{% extends "auth/base_auth.html" %}

{% block title %}Sign In — 4MAN Services Pro{% endblock %}

{% block content %}
<h2 class="auth-split__title">Welcome back</h2>
<p class="auth-split__description">Sign in to manage your jobs and team</p>

<form method="POST" action="{{ url_for('auth.login') }}">
    <div class="auth-split__form-group">
        <label for="email">Email Address</label>
        <input type="email" id="email" name="email" placeholder="you@yourcompany.com" required autofocus>
    </div>

    <div class="auth-split__form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" placeholder="Enter your password" required>
    </div>

    <div class="auth-split__form-group" style="display: flex; justify-content: space-between; align-items: center;">
        <label style="display:flex;align-items:center;gap:0.5rem;font-weight:400;color:var(--color-text-secondary);cursor:pointer;">
            <input type="checkbox" id="remember" name="remember" style="accent-color: var(--color-accent);">
            Remember me
        </label>
        <a href="{{ url_for('auth.forgot_password') }}" style="font-size: 0.85rem;">Forgot password?</a>
    </div>

    <button type="submit" class="auth-split__btn">Sign In</button>
</form>

<a href="{{ url_for('auth.demo') }}" class="auth-split__btn auth-split__btn--secondary"
   style="display:inline-block;text-align:center;text-decoration:none;">
    Try Demo Version
</a>
<p style="font-size: 0.75rem; color: var(--color-text-muted); margin-top: 0.5rem; text-align: center;">
    Pre-loaded with sample data — no sign-up needed
</p>

<div class="auth-split__links">
    <p style="margin-bottom: 0.5rem;">Don't have an account?</p>
    <a href="{{ url_for('auth.register') }}">Create an account</a>
</div>
{% endblock %}
```

Important: form action URL (`{{ url_for('auth.login') }}`), input `name=` attributes (`email`, `password`, `remember`), and submit button (`type="submit"`) are unchanged.

- [ ] **Step 3: Update `auth/register.html`**

Replace the entire contents of `web/templates/auth/register.html` with:

```html
{% extends "auth/base_auth.html" %}

{% block title %}Create Account — 4MAN Services Pro{% endblock %}

{% block content %}
<h2 class="auth-split__title">Create your account</h2>
<p class="auth-split__description">Get your team dispatched and jobs tracked</p>

<form method="POST" action="{{ url_for('auth.register') }}">
    <div class="auth-split__form-row">
        <div class="auth-split__form-group">
            <label for="first_name">First Name</label>
            <input type="text" id="first_name" name="first_name" placeholder="Ricky" required>
        </div>
        <div class="auth-split__form-group">
            <label for="last_name">Last Name</label>
            <input type="text" id="last_name" name="last_name" placeholder="Smith">
        </div>
    </div>

    <div class="auth-split__form-group">
        <label for="company_name">Company Name</label>
        <input type="text" id="company_name" name="company_name" placeholder="Acme Plumbing Inc." required>
    </div>

    <div class="auth-split__form-group">
        <label for="email">Work Email</label>
        <input type="email" id="email" name="email" placeholder="you@yourcompany.com" required>
    </div>

    <div class="auth-split__form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" placeholder="At least 8 characters" required minlength="8">
        <div class="auth-split__password-strength">
            <div class="auth-split__password-strength-bar" id="strengthBar"></div>
        </div>
    </div>

    <div class="auth-split__form-group">
        <label for="confirm_password">Confirm Password</label>
        <input type="password" id="confirm_password" name="confirm_password" placeholder="Re-enter your password" required>
    </div>

    <button type="submit" class="auth-split__btn">Create Account</button>
</form>

<div class="auth-split__links">
    <p style="margin-bottom: 0.5rem;">Already have an account?</p>
    <a href="{{ url_for('auth.login') }}">Sign in</a>
</div>

<script>
    const passwordInput = document.getElementById('password');
    const strengthBar = document.getElementById('strengthBar');
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        let strength = 0;
        if (password.length >= 8) strength++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
        if (/\d/.test(password)) strength++;
        if (/[^a-zA-Z0-9]/.test(password)) strength++;
        strengthBar.className = 'auth-split__password-strength-bar';
        if (strength <= 1) strengthBar.classList.add('strength-weak');
        else if (strength <= 2) strengthBar.classList.add('strength-medium');
        else strengthBar.classList.add('strength-strong');
    });
</script>
{% endblock %}
```

Form action, input names, JS behavior all unchanged.

- [ ] **Step 4: Browser smoke check**

Visit `/login` (logged out — open an incognito window). You should see: cream parchment left panel with the gold gear logo and "4MAN" / "SERVICES" / "PRO" wordmark + "JOBS · INVOICING · MANAGEMENT" tagline. Right panel: white background, "Welcome back" heading, email/password form with gold "Sign In" button (navy text). Try submitting with valid credentials — you should be logged in. Visit `/register` — same split-screen with the registration form.

- [ ] **Step 5: Commit**

```bash
git add web/templates/auth/base_auth.html web/templates/auth/login.html web/templates/auth/register.html
git commit -m "rebrand: auth pages use split-screen with cream brand panel + gold form"
```

---

## Task 8: Portal login — split-screen + portal/base.html title fix

**Files:**
- Modify: `web/templates/portal/auth/login.html`
- Modify: `web/templates/portal/base.html`

- [ ] **Step 1: Rewrite `portal/auth/login.html`**

Replace the entire contents of `web/templates/portal/auth/login.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0d1b3d">
    <title>Client Portal Login — 4MAN Services Pro</title>
    <link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='img/4man-logo.svg') }}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/variables.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body style="font-family: var(--font-family);">
{% from 'partials/_brand.html' import hero_lockup %}
<div class="auth-split">

    <aside class="auth-split__brand">
        <div></div>
        <div class="auth-split__brand-inner">
            {{ hero_lockup(tagline=true, subhead="Manage your services, view invoices, and stay informed") }}
        </div>
        <div class="auth-split__brand-footer">
            &copy; 2026 4MAN Services Pro &middot; All rights reserved
        </div>
    </aside>

    <main class="auth-split__form">
        <div class="auth-split__form-card">
            <h2 class="auth-split__title">Client Portal</h2>
            <p class="auth-split__description">Sign in to manage your services</p>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    <div class="auth-split__flash">
                        {% for category, message in messages %}
                            <div class="flash flash-{{ category if category != 'message' else 'info' }}">{{ message }}</div>
                        {% endfor %}
                    </div>
                {% endif %}
            {% endwith %}

            <form method="POST" action="{{ url_for('portal_auth.portal_login') }}">
                <div class="auth-split__form-group">
                    <label for="email"><i class="bi bi-envelope" aria-hidden="true"></i> Email Address</label>
                    <input type="email" id="email" name="email" placeholder="your@email.com" required autofocus>
                </div>

                <div class="auth-split__form-group">
                    <label for="password"><i class="bi bi-lock" aria-hidden="true"></i> Password</label>
                    <input type="password" id="password" name="password" placeholder="Enter your password" required>
                </div>

                <div style="text-align:right;margin-bottom:var(--space-4);">
                    <a href="{{ url_for('portal_auth.portal_forgot_password') }}"
                       style="font-size:0.85rem;">Forgot password?</a>
                </div>

                <button type="submit" class="auth-split__btn">
                    <i class="bi bi-box-arrow-in-right" aria-hidden="true"></i> Sign In
                </button>
            </form>
        </div>
    </main>

</div>
</body>
</html>
```

Form action (`{{ url_for('portal_auth.portal_login') }}`), input names (`email`, `password`), and the forgot-password URL (`{{ url_for('portal_auth.portal_forgot_password') }}`) all unchanged.

- [ ] **Step 2: Update `portal/base.html` title**

In `web/templates/portal/base.html`, replace line 6:

```html
    <title>{% block title %}Client Portal{% endblock %} — FieldServicePro</title>
```

with:

```html
    <title>{% block title %}Client Portal{% endblock %} — 4MAN Services Pro</title>
```

- [ ] **Step 3: Browser smoke check**

Visit `/portal/login`. Same split-screen treatment as the staff login. Submit valid portal credentials — should log you in. The inner portal pages (after login) keep their existing blue palette — that's intentional for now.

- [ ] **Step 4: Commit**

```bash
git add web/templates/portal/auth/login.html web/templates/portal/base.html
git commit -m "rebrand: portal login uses split-screen 4MAN brand; portal title"
```

---

## Task 9: Error pages

**Files:**
- Modify: `web/templates/errors/403.html`
- Modify: `web/templates/errors/500.html`

These extend `base.html`, so they auto-inherit the new tokens. We only need to make sure the page-title text is consistent and add a brand touch (gold gear icon instead of generic warning icon).

- [ ] **Step 1: Update `errors/403.html`**

Replace the entire contents of `web/templates/errors/403.html` with:

```html
{% extends "base.html" %}
{% block title %}Access Denied{% endblock %}
{% block page_title %}Access Denied{% endblock %}

{% block content %}
<div class="empty-state" style="padding: var(--space-12) var(--space-6); text-align: center;">
  <i class="bi bi-shield-lock" style="display: block; font-size: 3rem; color: var(--color-warning); margin-bottom: var(--space-4);"></i>
  <h3 style="font-size: var(--font-size-xl); color: var(--color-primary);">Access Denied</h3>
  <p style="color: var(--color-text-secondary);">You don't have permission to access this page.</p>
  <a href="{{ url_for('dashboard') }}" class="btn btn-primary" style="margin-top: var(--space-4);">
    <i class="bi bi-house" aria-hidden="true"></i> Go to Dashboard
  </a>
</div>
{% endblock %}
```

Changes only: heading colors, icon color shifted from danger-red to warning-orange (better tone for permission errors), button class `btn-accent` → `btn-primary` (which Task 5 made the gold variant).

- [ ] **Step 2: Update `errors/500.html`**

Replace the entire contents of `web/templates/errors/500.html` with:

```html
{% extends "base.html" %}
{% block title %}Something went wrong{% endblock %}
{% block page_title %}Server Error{% endblock %}

{% block content %}
<div class="empty-state" style="padding: var(--space-12) var(--space-6); text-align: center;">
  <i class="bi bi-exclamation-octagon" style="display: block; font-size: 3rem; color: var(--color-danger); margin-bottom: var(--space-4);"></i>
  <h3 style="font-size: var(--font-size-xl); color: var(--color-primary);">Something went wrong</h3>
  <p style="color: var(--color-text-secondary);">An unexpected error occurred. The team has been notified — please try again in a moment.</p>
  <a href="{{ url_for('dashboard') }}" class="btn btn-primary" style="margin-top: var(--space-4);">
    <i class="bi bi-house" aria-hidden="true"></i> Go to Dashboard
  </a>
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add web/templates/errors/403.html web/templates/errors/500.html
git commit -m "rebrand: 403/500 error pages use new palette"
```

---

## Task 10: Email base template

**Files:**
- Modify: `web/templates/portal/email/base_email.html`

Email clients strip `<link>` tags so we cannot use Google Fonts in emails. Use Georgia (the declared fallback) for the brand title — it's email-safe and reads classical-serif.

- [ ] **Step 1: Replace `portal/email/base_email.html`**

Replace the entire contents of `web/templates/portal/email/base_email.html` with:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f5ecd7;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:20px auto;background:white;border-radius:9px;box-shadow:0 1px 3px rgba(0,0,0,0.1);overflow:hidden;">
        <tr>
            <td style="padding:28px 32px;background:#0d1b3d;">
                <table cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="vertical-align:middle;padding-right:14px;">
                            <img src="cid:4man-logo" alt="4MAN Services Pro" width="40" height="40" style="display:block;border:0;"
                                 onerror="this.style.display='none';">
                        </td>
                        <td style="vertical-align:middle;">
                            <div style="font-family:Georgia,'Times New Roman',serif;color:#e3b53a;font-size:20px;font-weight:700;letter-spacing:0.04em;line-height:1;">4MAN</div>
                            <div style="font-family:Arial,sans-serif;color:#ffffff;font-size:11px;font-weight:500;letter-spacing:0.12em;text-transform:uppercase;margin-top:3px;">Services Pro</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding:32px;color:#0d1b3d;font-size:14px;line-height:1.6;">
                {% block content %}{% endblock %}
            </td>
        </tr>
        <tr>
            <td style="padding:16px 32px;background:#f5ecd7;border-top:1px solid #e6d9b8;font-size:11px;color:#64748b;text-align:center;letter-spacing:0.05em;">
                JOBS &middot; INVOICING &middot; MANAGEMENT<br>
                <span style="color:#94a3b8;">This is an automated notification from 4MAN Services Pro.</span>
            </td>
        </tr>
    </table>
</body>
</html>
```

The `<img>` tag uses `cid:4man-logo` which expects an embedded image attachment. If the email-sending code does not attach images by CID (most likely it doesn't), the `onerror` hides the image and the wordmark text alone displays — which is the safe degradation. **Do not modify the email-sending Python code in this branch.**

- [ ] **Step 2: Commit**

```bash
git add web/templates/portal/email/base_email.html
git commit -m "rebrand: email base template uses navy + gold + cream"
```

---

## Task 11: String sweep for any missed "FieldServicePro" references

**Files:**
- Various templates surfaced by grep

- [ ] **Step 1: Grep for remaining occurrences**

Run from project root:

```bash
grep -rn "FieldServicePro" web/templates/ web/static/
```

Expected: a list of every remaining file that mentions the old name in user-visible content.

- [ ] **Step 2: For each file in the grep output, replace `FieldServicePro` with `4MAN Services Pro`**

Open each file. For each match:
- If it's in a `<title>`, `<meta>`, comment, alt text, copyright line, or other user-visible string: replace with `4MAN Services Pro`.
- If it's a comment header like `/* FieldServicePro — Component Stylesheet */`: replace with `4MAN Services Pro — Component Stylesheet`.
- If it's a Python class/variable name (e.g., `FieldServicePro_db = ...`) — DO NOT change. Per scope, no `.py` edits. (But this grep is template+static only, so this shouldn't appear.)

Common files expected: top comment headers in CSS files, some template `<title>` blocks, some PDF templates.

- [ ] **Step 3: Re-run grep to confirm zero matches**

```bash
grep -rn "FieldServicePro" web/templates/ web/static/
```

Expected: no output.

- [ ] **Step 4: Also sweep `FieldService Pro` (with space)**

```bash
grep -rn "FieldService Pro" web/templates/ web/static/
grep -rn "Field Service Pro" web/templates/ web/static/
```

Replace any matches in the same way.

- [ ] **Step 5: Commit**

```bash
git add -u web/templates/ web/static/
git commit -m "rebrand: sweep remaining FieldServicePro references → 4MAN Services Pro"
```

---

## Task 12: Verification pass

No commits in this task — purely smoke tests against the running app.

- [ ] **Step 1: Confirm zero `.py` files changed**

```bash
git diff master --name-only | grep -E '\.py$'
```

Expected: empty output. Any `.py` in the diff means we accidentally changed behavior; investigate before merging.

- [ ] **Step 2: Confirm string sweep is complete**

```bash
grep -rn "FieldServicePro" web/templates/ web/static/ docs/
```

Expected: only matches inside `docs/superpowers/specs/2026-04-16-*` (historical specs, leave as-is). Zero matches in templates or static assets.

- [ ] **Step 3: Boot the dev server and walk every major surface**

Start the dev server. In a clean browser session:

1. Visit `/` → should redirect to `/login`. Login screen renders split-screen with cream brand panel + white form. Gold "Sign In" button.
2. Submit valid credentials. Lands on `/dashboard`.
3. Sidebar shows gold gear + "4MAN" / "Services Pro" wordmark. Active nav item has gold left-edge accent.
4. Click through: Jobs, Schedule, Clients, Invoices, Quotes, Settings. Each loads, no broken layouts, no teal residue.
5. Click an "Edit" button on a record — gold button, navy text. Hover should brighten the gold.
6. Open the AI Assistant FAB (bottom right). Should be gold circle with white robot icon.
7. Click a sidebar badge — appropriate color (gold for accent badges, orange for warnings, red for danger, green for success).
8. Trigger a 403 (visit a route you don't have permission for) or hit a known 500. Confirm error page renders with the navy heading + gold "Go to Dashboard" button.
9. Log out. Log into `/portal/login` (use a portal account if you have one). Same split-screen treatment.
10. Visit `/booking/<some-key>` if you have a public booking URL. Should still show the *org's* brand (this is intentional — see deviation note).
11. (Optional) Trigger a notification email and view it. Header shows navy with gold "4MAN" text.

- [ ] **Step 4: Mobile responsiveness check**

In browser dev tools, set viewport to 375px (iPhone SE) and reload `/login`. Split-screen should collapse to single column — brand panel becomes a compact top band, form below. Test that you can submit the form. Set viewport to 768px (iPad) and confirm the split-screen kicks in.

- [ ] **Step 5: Final diff summary**

```bash
git log master..HEAD --oneline
git diff master --stat
```

Confirm: ~10–12 commits, all CSS/HTML/SVG, no .py.

---

## Self-Review (post-write)

**Spec coverage check:**
- ✅ Color tokens (Task 1)
- ✅ Typography (Task 1, Task 3 fonts link)
- ✅ Logo system / inline SVG mark (Task 2)
- ✅ Sidebar surface treatment (Task 4)
- ✅ Component restyles (button, badge, link) (Task 5)
- ✅ Login split-screen redesign (Task 7)
- ✅ Portal login (Task 8)
- ✅ Error pages (Task 9)
- ✅ Email base (Task 10)
- ✅ Brand string sweep (Task 11)
- ✅ Verification (Task 12)
- ⚠️ **Booking** — explicitly deferred (see plan header). Spec said "booking landing reuses cream brand surface treatment" but real code is tenant-branded. Deviation called out.

**Placeholder scan:** No "TODO", "TBD", "implement later" in the plan. Every code block contains the actual content.

**Type/name consistency:** Class names used in plans match across tasks (e.g., `auth-split__btn` defined in Task 6 and used in Tasks 7 and 8; `brand-hero-lockup__line1` used in Task 6 media query and produced by macro in Task 2). Macros `mark`, `sidebar_lockup`, `hero_lockup` defined in Task 2 and consumed in Tasks 4, 7, 8.

**One known soft spot:** Task 5 step 3 ("update body link color") leaves room for judgment about whether existing rules already do the right thing. This is intentional — the components.css file is large and it's faster for the executor to read it than for me to dictate every line. The acceptance criterion is "links on white surfaces are navy."
