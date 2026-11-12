"""Stage CDN assets and the precomputed school cache before Vercel bundles Flask."""
import os
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

from app.services import dashboard_v4  # noqa: E402

DEFAULT_CACHE_URL = (
    "https://github.com/rtritz/trackinsights/releases/download/"
    "cache-latest/dashboard_cache.db"
)


def main():
    cache_path = ROOT / "web/data/dashboard_cache.db"
    status = dashboard_v4.cache_status()
    if not status["built"] or status["stale"]:
        url = os.environ.get("DASHBOARD_CACHE_URL", DEFAULT_CACHE_URL)
        temporary = cache_path.with_suffix(".download")
        print("Downloading precomputed school dashboard cache...", flush=True)
        try:
            with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(cache_path)
        finally:
            temporary.unlink(missing_ok=True)
        status = dashboard_v4.cache_status()
    if not status["built"] or status["stale"]:
        raise RuntimeError(
            "School dashboard cache does not match Track.db. Publish a matching "
            "cache and set DASHBOARD_CACHE_URL to its download URL."
        )
    print("School dashboard cache matches Track.db.", flush=True)

    # Preserve /static/... URLs used by url_for and the card renderer.
    shutil.copytree(ROOT / "web/app/static", ROOT / "public/static", dirs_exist_ok=True)
    print("Static assets staged in public/static.", flush=True)


if __name__ == "__main__":
    main()
