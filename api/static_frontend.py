"""Serve the built Vite frontend from FastAPI for local production mode.

This is what lets a single origin (http://127.0.0.1:8000) serve both the app and
the API. It is opt-in: `create_app()` mounts nothing unless a dist directory is
supplied, so the API-only behavior the tests rely on is unchanged.

Route precedence matters. Routers are registered before this, and every API
route lives under `/api`, so the SPA catch-all can never shadow one. Unknown
`/api/...` paths must still 404 as JSON rather than fall through to index.html.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def dist_is_built(dist_dir: Path) -> bool:
    return (dist_dir / "index.html").is_file()


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Mount `dist_dir` assets and add an SPA fallback to index.html."""
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(f"No built frontend at {dist_dir}")

    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        # Hashed filenames, so a long-lived mount is safe.
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve a real file when one exists, else index.html for deep links."""
        if full_path.startswith("api/") or full_path == "api":
            # Never let an unmatched API path render the SPA shell.
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = _safe_candidate(dist_dir, full_path)
        if candidate is not None and candidate.is_file():
            return FileResponse(candidate)

        # A missing asset is a genuine 404, not a deep link.
        if _looks_like_asset(full_path):
            raise HTTPException(status_code=404, detail="Not Found")

        return FileResponse(index_path)


def _safe_candidate(dist_dir: Path, full_path: str) -> Path | None:
    """Resolve `full_path` inside `dist_dir`, or None if it escapes the root."""
    if not full_path:
        return None
    candidate = (dist_dir / full_path).resolve()
    root = dist_dir.resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    return None


def _looks_like_asset(full_path: str) -> bool:
    """True for paths that name a file, so a typo'd asset 404s honestly.

    SPA routes are extensionless (`/projects/abc`); assets carry a suffix
    (`/missing.js`, `/favicon.ico`).
    """
    last_segment = full_path.rsplit("/", 1)[-1]
    return "." in last_segment
