# 4MAN Services Pro — Visual Rebrand Design Spec

**Branch:** `4MAN-SERVICES-PRO`
**Date:** 2026-04-27
**Scope:** Aesthetics-only rebrand from "FieldServicePro" to "4MAN Services Pro"
**Out of scope:** Any change to routes, models, business logic, form behavior, JavaScript behavior, database schema, env vars, or template control flow

---

## Goal

Replace the existing FieldServicePro visual identity with the new 4MAN Services Pro brand (navy + gold, classic-industrial feel) across every user-visible surface, without modifying any functional code. Inspired by the provided logo: gear/sun mark on navy, serif "4MAN SERVICES" wordmark with gold "PRO" pill, tagline "JOBS · INVOICING · MANAGEMENT".

## Constraints

- **Aesthetics only.** No `.py` files modified. No changes to `url_for()` calls, form actions, field names, control flow, or JavaScript behavior.
- **Surgical token-driven approach.** Concentrate the rebrand in `web/static/css/variables.css` and rely on the existing design-token system to propagate changes.
- **Don't introduce new behavior.** No dark mode, no density toggles, no layout reorganization, no new routes.
- **Reversible.** A clean revert of the branch must restore the prior look exactly.

---

## Color Tokens

Replace the following entries in `web/static/css/variables.css`. All other tokens (spacing, radii, shadows, font sizes, z-index) stay unchanged.

| Token | Current | New | Purpose |
|---|---|---|---|
| `--color-primary` | `#1e293b` | `#0d1b3d` | Deep navy — sidebar bg, brand text |
| `--color-primary-light` | `#334155` | `#1e2d5c` | Hover/raised navy |
| `--color-primary-dark` | `#0f172a` | `#06122b` | Pressed navy |
| `--color-accent` | `#0d9488` | `#e3b53a` | Brand gold — buttons, links, active nav |
| `--color-accent-light` | `#14b8a6` | `#f1c95b` | Hover gold |
| `--color-accent-dark` | `#0f766e` | `#b8902a` | Pressed gold |
| `--color-warning` | `#f59e0b` | `#ea580c` | Orange (shifted to stay distinct from gold) |
| `--color-warning-light` | `#fde68a` | `#fed7aa` | |
| `--color-warning-dark` | `#d97706` | `#c2410c` | |
| `--color-text-primary` | `#1e293b` | `#0d1b3d` | Match new navy |
| `--sidebar-bg` | `var(--color-primary)` | unchanged (auto-updates via primary) | |
| `--sidebar-icon-active` | `var(--color-accent-light)` | unchanged (auto-updates via accent) | |
| `--sidebar-active-bg` | `rgba(13,148,136,0.15)` | `rgba(227,181,58,0.15)` | Gold glow |

**New tokens added:**

| Token | Value | Purpose |
|---|---|---|
| `--color-cream` | `#f5ecd7` | Parchment background for auth/portal/booking/error pages |
| `--color-cream-border` | `#e6d9b8` | Warm border on cream surfaces |
| `--font-family-display` | `'Playfair Display', Georgia, serif` | Brand wordmark and hero headings only |

`--color-success` and `--color-danger` are unchanged. `--color-bg` (`#f8fafc`) for app interior is unchanged.

## Typography

Two-font system. Inter remains the default everywhere; Playfair Display is added strictly for brand surfaces.

| Role | Font | Where |
|---|---|---|
| Brand display | Playfair Display 700 | Hero login lockup wordmark, sidebar wordmark, email header, portal/booking lockup |
| UI / body | Inter (existing) | Page titles in app, tables, forms, buttons, sidebar nav, all body copy |

Add the Playfair Display weight to the existing Google Fonts `<link>` in `base.html`, `auth/base_auth.html`, `portal/base.html`, `booking/base.html`, and `portal/email/base_email.html`.

Do **not** apply the serif inside the app proper (dashboard, jobs, schedule, tables, forms, modals). Inter stays for readability.

## Logo System

The mark is rebuilt as inline SVG and packaged in a reusable Jinja partial.

**The mark:** a 12-rayed gear/sun ring in gold (`#e3b53a`) around a central gold disc with a small navy dot, on a navy (`#0d1b3d`) rounded square (radius ~14% of viewBox). One SVG source, scaled via `viewBox` for every use.

**Three variants generated from the same source:**

| Variant | Where used | Composition |
|---|---|---|
| Mark only | Favicon, app icons, theme-color | Gear ring on navy rounded square |
| Sidebar lockup | `partials/sidebar.html` | 28px mark + Playfair "4MAN" stacked over Inter "Services Pro" |
| Hero lockup | Login, portal login, booking landing, email header, error pages | 96px+ mark + serif "4MAN" / gold rule / "SERVICES" / "PRO" pill, with tagline "JOBS · INVOICING · MANAGEMENT" beneath |

**On dark backgrounds** (sidebar, navy hero panels): the mark renders as gold on transparent (no navy square) so the gear pops.

**On light backgrounds** (cream, white): the mark renders with the full navy rounded square.

**Files:**

- New: `web/templates/partials/_brand.html` — defines three Jinja macros (`mark`, `sidebar_lockup`, `hero_lockup`) so any template can include the right variant
- New: `web/static/img/4man-logo.svg` — standalone SVG file for places that need a real URL (PDF generation, OG image meta, email clients that strip inline SVG)
- Existing: replace inline favicon SVG in `base.html`, replace inline mark + wordmark in `partials/sidebar.html`

## Surface Treatment

Three zones with distinct visual treatment:

| Zone | Background | Type system | Accent |
|---|---|---|---|
| App interior (authenticated) | White cards on `#f8fafc` | Inter | Gold |
| Brand surfaces (auth, portal login, booking, error pages, emails) | Cream `#f5ecd7` | Playfair display + Inter body | Gold + navy |
| Sidebar | Deep navy `#0d1b3d` | Inter sans + small Playfair wordmark | Gold |

**Specific component changes:**

- **Sidebar active state.** Today: soft teal glow on left edge. New: 3px solid gold left-edge bar plus subtle gold-tinted background (`rgba(227,181,58,0.15)`). Active icon color changes from teal-light to gold-light.
- **Primary buttons.** Background `#e3b53a` gold, text `#0d1b3d` navy, no border. Hover: `#f1c95b`. Active: `#b8902a`. The current teal primary button styles in `components.css` get retargeted.
- **Secondary/outline buttons.** Navy 1px border, navy text, transparent background. Hover: navy bg, white text.
- **Body links.** Inside app interior: navy (gold-on-white fails contrast). On cream surfaces: navy. Underline-on-hover preserved.
- **Page titles inside the app.** Stay Inter, color updated to new navy. Not serif.
- **Card borders.** `#e2e8f0` slate → `#e6d9b8` warm border so cards harmonize with cream surfaces nearby.
- **Shadow tokens.** Unchanged.
- **AI assistant FAB.** Background changes from teal to gold; icon stays as `bi-robot`.
- **Badges.** Teal badges → gold; amber warning badges → orange (new warning hex). Danger and success badges unchanged.

**Out of scope:** Dark mode. Density toggles. Layout changes to existing pages. Sidebar group reorganization. Chart restyles. Dashboard widget changes.

## Login & Auth Redesign (split-screen)

Applies to `auth/login.html`, `auth/register.html`, `portal/auth/login.html`. The `auth/base_auth.html` template is updated to support the new layout.

**Layout:**

- ≥768px viewports: two equal columns side by side
- <768px: single column, brand panel collapses to a compact top band, form below

**Left column — brand panel (cream):**

- Hero logo lockup centered
- Tagline "JOBS · INVOICING · MANAGEMENT" in small Inter caps, navy
- One-line subhead "Field service management built for modern operations"
- Small footer line "© 2026 4MAN Services Pro · All rights reserved"

**Right column — form panel (white):**

- Existing form markup retained verbatim — same fields, same `action`, same `name=` attributes, same flash-message rendering, same submit handlers
- Restyling only: navy labels, gold primary submit button with navy text, navy text links

The booking landing (`booking/base.html`) and the existing error pages (`errors/403.html`, `errors/500.html`) reuse the cream brand surface treatment with the hero lockup centered, body message in Inter, optional CTA button. (404 is handled by a flash + redirect in `app.py:759` — no template exists, and we are not adding one in this branch since that would change behavior.)

## Brand Strings & Meta Tags

Cosmetic find-and-replace pass. Strings to update:

| From | To | Where |
|---|---|---|
| `FieldServicePro` | `4MAN Services Pro` | `<title>` blocks, `<meta name="description">`, `apple-mobile-web-app-title`, sidebar wordmark, email subjects and signatures, PDF footers, "© FieldServicePro" copyright lines |
| `theme-color` `#1e293b` | `#0d1b3d` | `base.html`, any other base templates that set theme-color |

Wordmark structure in templates is updated so "4MAN" gets the Playfair display class and "Services Pro" gets the Inter class — matches the logo's typographic hierarchy.

**Final state check:** `grep -r "FieldServicePro" web/ docs/` should return zero matches except in:

- Deploy/readiness historical docs in `docs/superpowers/specs/2026-04-16-*` (historical, leave intact)
- Any database seed data containing the old name (none expected, but if found, leave for a separate data migration outside this branch)

## Files Modified

**CSS (3 files):**

- `web/static/css/variables.css` — token replacements + new cream / display-font tokens
- `web/static/css/components.css` — button restyles, brand-surface utility class (`.brand-surface`), updated active-nav state
- `web/static/css/style.css` — split-screen auth layout, hero-lockup styles, error-page treatment

**Templates (~15 files, all visual edits only):**

- New: `web/templates/partials/_brand.html`
- Modified: `web/templates/base.html`, `web/templates/partials/sidebar.html`, `web/templates/auth/base_auth.html`, `web/templates/auth/login.html`, `web/templates/auth/register.html`, `web/templates/portal/base.html`, `web/templates/portal/auth/login.html`, `web/templates/booking/base.html`, `web/templates/errors/403.html`, `web/templates/errors/500.html`, `web/templates/portal/email/base_email.html`

**Assets (1 new file):**

- New: `web/static/img/4man-logo.svg`

**Strings:** A grep-driven pass for `FieldServicePro` → `4MAN Services Pro` across the templates above (plus any others surfaced by grep that contain the old string in user-visible content).

**Files explicitly NOT modified:**

- Anything under `web/routes/`, `models/`, top-level `*.py`
- `requirements.txt`, `render.yaml`, `Procfile`, env config
- Any `.js` file in `web/static/js/` (behavior preserved)
- Form HTML control flow (`<form action>`, `name=`, `{% csrf_token %}` blocks)
- Database migrations or seed data

## Verification

After the implementation pass, before merging:

1. **Token sanity.** Boot the dev server, log in, visit dashboard, jobs, schedule, clients, invoices, settings. Confirm: no broken layouts, all text is legible (gold-on-navy, navy-on-cream, navy-on-white), no green/teal accent leftovers, sidebar active state is gold not teal.
2. **Auth + portal + booking + errors smoke test.** Visit `/login`, `/register`, `/portal/login`, a `/booking/<key>` URL, and trigger a 403/500 if possible. (Hitting an unknown URL flashes "Page not found" and redirects — that's existing behavior and stays.) Confirm: split-screen renders, hero lockup is crisp at all sizes, forms still submit successfully (test login with real credentials).
3. **String sweep.** `grep -ri "FieldServicePro" web/` returns no user-visible matches.
4. **No-functional-change diff check.** `git diff master --name-only` shows only `*.css`, `*.html`, `*.svg` files. Zero `.py` files.
5. **Email preview.** Send a test password-reset or notification email; confirm the new logo and brand renders correctly in at least Gmail and Outlook web clients.
6. **Mobile responsiveness.** At 375px (iPhone SE) and 768px (iPad portrait), confirm split-screen collapses correctly and the sidebar mobile drawer still works.

## Implementation Order

The implementation plan (next phase) will sequence work as:

1. Token swap in `variables.css` — biggest blast radius, do first to surface any contrast issues immediately
2. Build `_brand.html` partial + standalone `4man-logo.svg`
3. Update `base.html` (favicon, fonts, theme-color, title)
4. Update `partials/sidebar.html` (lockup + active-state styles)
5. Component pass in `components.css` (buttons, badges, links, active states)
6. Auth/portal/booking split-screen redesign
7. Error pages
8. Email base template
9. String sweep for `FieldServicePro`
10. Verification pass
