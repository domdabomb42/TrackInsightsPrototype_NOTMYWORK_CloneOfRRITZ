# Deploy the prototype to Vercel

1. Import `domdabomb42/TrackInsightsPrototype_NOTMYWORK_CloneOfRRITZ` in Vercel.
2. Use the **Flask** framework and repository root (`.`), not `web/`.
3. Select `local-edits` as the production branch (Settings → Environments → Production).
4. Leave install settings at their defaults and keep the build command from
   `vercel.json`: `python scripts/build_vercel.py`.
5. Set `SECRET_KEY` to a randomly generated secret in Vercel environment variables.
6. Deploy. Check the homepage, search, athlete and school dashboards, and a card PNG.

The root `wsgi.py` exports Flask and adds `web/` to Python's import path. Python
dependencies are declared in `pyproject.toml`. Static assets are copied into
`public/static` during the build so existing `/static/...` URLs use Vercel's CDN.
The function also includes `web/` and `common/` for templates, card fonts and logos,
precomputed data, and SQLite files.

The deployment serves the committed database snapshot. Update results locally,
rebuild the derived data, and redeploy; this setup does not persist runtime writes.
Athlete card PNGs are rendered in memory.

School dashboards require the generated `dashboard_cache.db`, which is not in Git.
The build downloads the upstream `cache-latest` release asset and checks it against
the bundled Track.db. If they no longer match, the build fails rather than serving
empty/stale school dashboards. Publish a matching cache to your own release and
set `DASHBOARD_CACHE_URL` to its public download URL. A matching local cache is
also accepted for CLI builds. See PROJECT_GUIDE.md for rebuilding that cache.

Local smoke check from the repository root:

```powershell
.venv/Scripts/python.exe scripts/build_vercel.py
.venv/Scripts/python.exe -c "from wsgi import app; print(app.test_client().get('/').status_code)"
```
