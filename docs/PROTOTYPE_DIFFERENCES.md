# Prototype differences from upstream athlete-cards

Comparison date: November 12, 2026.

| Item | Compared version |
| --- | --- |
| Prototype repository | [domdabomb42/TrackInsightsPrototype_NOTMYWORK_CloneOfRRITZ](https://github.com/domdabomb42/TrackInsightsPrototype_NOTMYWORK_CloneOfRRITZ) |
| Prototype branch | `local-edits` |
| Prototype commit | `0aeb7ffb18b21e541c1dcd5f21f97eb65934f997` |
| Original repository | [rtritz/trackinsights](https://github.com/rtritz/trackinsights) |
| Original branch | `athlete-cards` |
| Original commit | `2b7f0238c474545382a70fc0ae5930f2b36d0248` |

The upstream branch was fetched immediately before this comparison. The prototype
contains all commits from that upstream revision plus 10 additional commits.
The net difference is **19 files: 5 added, 14 modified, none deleted; 246 lines
added and 21 removed**. These counts exclude this report, which is itself a new
documentation file added after the compared prototype revision.

This report describes the final differences in Git, rather than every request or
intermediate design tried during development. Local generated files and hosting
account settings are outside the comparison.

## 1. Vercel deployment support

- Added a root `wsgi.py` entry point exporting Flask as `app`. It adds `web/` to
  Python's import path so the existing application and configuration imports work.
  The original `web/wsgi.py` remains unchanged.
- Added `vercel.json`: Flask framework, `python scripts/build_vercel.py` build
  command, 60-second function duration, and explicit inclusion of `web/**` and
  `common/**` in the function bundle.
- Added Flask, Flask-SQLAlchemy, Pillow, and NumPy to the default dependencies in
  `pyproject.toml`, so installation does not depend on selecting the web extras.
  Existing optional dependency groups remain. Added `tool.vercel.entrypoint` as
  `wsgi:app`.
- Added `scripts/build_vercel.py`. It checks the school-dashboard cache; if missing
  or stale, it downloads `dashboard_cache.db` from the original repository's
  `cache-latest` release, or from `DASHBOARD_CACHE_URL` when configured. It fails
  the build if the downloaded cache does not match the bundled results database.
  It also copies static assets to `public/static` for Vercel's CDN, preserving
  existing `/static/...` URLs.
- Added `.vercelignore` to exclude standalone tools, tests, docs, virtual
  environments, pytest caches, and Python bytecode caches from deployment uploads.
- Added `.vercel/` and generated `public/` output to `.gitignore`.
- Added `docs/VERCEL.md` with import settings, environment variables, deployment
  checks, cache handling, and local smoke-check instructions.

The prototype serves the committed SQLite snapshot. This deployment setup does
not provide persistent runtime database writes or migrate the app to a new database.

## 2. Athlete card URL fix

`web/app/routes/main_routes.py` now retries a failed card lookup after decoding
percent escapes in the event name once. The exact event name is tried first.
This fixes hosted HTML previews and image/share routes when the host leaves an
event such as `400%20Meters` encoded in the route parameter.

The share page also builds PNG and sticker URLs using the canonical event name
from the retrieved card, avoiding double-encoded event names.

`tests/test_cards.py` adds three parameterized regression cases for an encoded
event name in `PATH_INFO`: HTML preview, PNG image, and share page.

## 3. Mobile card saving

- The athlete dashboard's mobile action is labeled **Add to Photos**, replacing
  upstream's **Save to Photos**. The label is set earlier, including when the
  dashboard has no cards or reports a card problem. Desktop retains **Download**.
- Supported mobile browsers continue to receive the PNG file through the native
  share sheet. The user must choose the browser/OS save action; the page cannot
  silently save into the photo library.
- When file sharing is unavailable, or fails for a reason other than cancellation,
  the prototype opens a dialog with the full-size card and touch-and-hold save
  instructions. Upstream instead falls back to a file download.
- Added dialog styling, image sizing, and object-URL cleanup on close.

## 4. Athlete dashboard personal bests and event folders

### Mobile personal bests

- At widths up to 767px, personal-best tiles use an automatically wrapping grid
  with a 104px minimum tile target, limited by available width.
- Times/marks use a non-wrapping value and container-relative font sizing.
- Labels reserve two lines. Relay labels split into a non-wrapping distance line
  such as `4 x 800`, followed by `Relay` on a separate line.
- Desktop relay labels remain inline; the splitting behavior is mobile-only.

### Folder labels

Upstream removes `Meters` from tab labels at every width. The prototype removes
it only at mobile widths (up to 767px), restores the full event name on desktop,
and updates the labels when the viewport crosses that breakpoint.

### Folder order

Upstream sorts event names alphabetically. The prototype uses this order, showing
only events available for the athlete:

1. 100 Meters
2. 100 Hurdles / 110 Hurdles (girls/boys respectively)
3. 4 x 100 Relay
4. 200 Meters
5. 300 Hurdles
6. 400 Meters
7. 4 x 400 Relay
8. 800 Meters
9. 4 x 800 Relay
10. 1600 Meters
11. 3200 Meters
12. Long Jump
13. High Jump
14. Pole Vault
15. Shot Put
16. Discus

Both sprint-hurdle events have explicit entries, with 100 Hurdles before 110
Hurdles if both appear. Unrecognized events follow the listed events and sort
alphabetically. Event names themselves are not renamed by this ordering change.

## 5. Home/About content and portrait

- Contact copy explicitly invites requests for track and field data, along with
  questions and feedback. Existing email and Instagram destinations remain.
- A disclaimer below Contact identifies the site as a working prototype, states
  that it was cloned from the working repository with explicit permission from
  Mr. Ritz, and links to the official site at `https://trackinsights.org`.
- Dominic G.'s portrait has a square crop wrapper with hidden overflow, a 1.25x
  image scale, and a transform origin of `50% 65%`, making the head appear larger
  relative to the other portraits. The actual image file is unchanged.
- README introduction identifies the repository as a temporary hosting clone,
  links to the original working repository, and links to the new Vercel guide.
  Its main heading also differs literally (`#Track Insights` versus upstream's
  `# Track Insights`).

## 6. Keyboard behavior

`web/app/static/js/main.js` adds an unmodified-arrow-key handler for ordinary page
text. Up/Down scroll the page by 48px; Left/Right prevent the default text-caret
movement. Already-handled events and keys with Alt, Ctrl, Meta, or Shift are left
alone. Inputs, textareas, selects, buttons, links, editable content, tabs, sliders,
and listboxes retain their own keyboard behavior. This is a page-level handler,
not a change to the browser's caret-browsing preference.

## 7. School and qualifier spacing

- Original school dashboard: replaced `pt-20 sm:pt-24` (80px/96px) with 24px of
  top padding on both mobile and desktop.
- V4 school dashboard: reduced top padding from 5.5rem to 24px. Its stylesheet
  cache-busting version now uses the CSS file's modification time, rather than
  the JavaScript file's modification time.
- Both Unofficial Regional and State Qualifiers pages: replaced `pt-20 sm:pt-24`
  with 24px of top padding, matching the event dashboard. The State Qualifiers
  template also gained a final newline.

## Complete changed-file inventory

| File | Status | Difference |
| --- | --- | --- |
| `.gitignore` | Modified | Ignore Vercel metadata and generated public assets. |
| `.vercelignore` | Added | Deployment upload exclusions. |
| `README.md` | Modified | Clone attribution, heading formatting, deployment-guide link. |
| `docs/VERCEL.md` | Added | Prototype deployment instructions. |
| `pyproject.toml` | Modified | Default web dependencies and Vercel entry point. |
| `scripts/build_vercel.py` | Added | Validate/download school cache and stage static assets. |
| `tests/test_cards.py` | Modified | Encoded event-name route regression cases. |
| `vercel.json` | Added | Framework, build command, function settings. |
| `web/app/routes/main_routes.py` | Modified | Decode card event names and use canonical share-image URLs. |
| `web/app/static/css/athlete-dashboard.css` | Modified | Mobile personal-best layout and photo-save dialog. |
| `web/app/static/css/school-dashboard-v4.css` | Modified | School top padding. |
| `web/app/static/js/athlete-dashboard.js` | Modified | Mobile saving, relay labels, responsive tab labels, event ordering. |
| `web/app/static/js/main.js` | Modified | Page-text arrow-key behavior. |
| `web/app/templates/home.html` | Modified | Portrait crop, contact copy, prototype disclaimer. |
| `web/app/templates/insights/regional-qualifiers.html` | Modified | Qualifier top spacing. |
| `web/app/templates/insights/state-qualifiers.html` | Modified | Qualifier top spacing and final newline. |
| `web/app/templates/school-dashboard-v4.html` | Modified | Correct CSS cache-busting source. |
| `web/app/templates/school-dashboard.html` | Modified | School top spacing. |
| `wsgi.py` | Added | Root Flask entry point for Vercel. |

## Already shared with upstream

Earlier work such as horizontal overlapping mobile folders, unlinked medals and
individual results, the Class Rank column, the Color toggle label, the mobile
share-section layout, the Search page simplification, larger homepage qualifier
buttons, and athlete/event/interview spacing is already present in the compared
upstream revision. These are not additional differences in this prototype.

No tracked database, portrait image, font, or other binary asset differs between
the two compared revisions. This report does not claim that the deployed servers
or ignored generated files are identical.

## Reproduce this comparison

```bash
git fetch origin athlete-cards
git diff --stat 2b7f0238c474545382a70fc0ae5930f2b36d0248 0aeb7ffb18b21e541c1dcd5f21f97eb65934f997
git diff 2b7f0238c474545382a70fc0ae5930f2b36d0248 0aeb7ffb18b21e541c1dcd5f21f97eb65934f997
```

To compare whatever revisions are current later, use `git diff origin/athlete-cards HEAD`;
that comparison will also include this report and any subsequent changes.
