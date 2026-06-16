"""Optional cinematic b-roll intro clip via the Pexels Video API (Fase 2.1).

Downloads ONE vertical stock clip themed on the product niche and returns its
local path (inside out/, gitignored). It is an OPTIONAL enhancement: when no
clip is available the caller falls back to the existing animated intro hook, so
the whole pipeline keeps working offline / in DRY_RUN with no API key.

Pexels licence: free for commercial use, no attribution required, no watermark.
See https://www.pexels.com/license/ . The API key (PEXELS_API_KEY) is read from
the environment and is NEVER committed.

Hard guarantee: fetch_intro_clip NEVER raises. Any missing key, network/HTTP
error, or empty result degrades to None.
"""
import os
from pathlib import Path

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"

# Vertical target (matches the 1080x1920 reel). We prefer a file close to this
# height, else the tallest portrait file available.
TARGET_W, TARGET_H = 1080, 1920

# Per-niche search queries (English; Pexels indexes in English).
_NICHE_QUERIES = {
    "electronics": "technology gadgets desk",
    "smart-home": "smart home interior",
    "sport": "fitness workout gym",
    "gadgets": "tech gadgets unboxing",
}
_DEFAULT_QUERY = "online shopping lifestyle"


def query_for_niche(niche: str) -> str:
    return _NICHE_QUERIES.get((niche or "").strip().lower(), _DEFAULT_QUERY)


def _pick_video_file(video: dict):
    """Choose the best vertical (portrait) file from a Pexels video result.

    Prefers the portrait file whose height is closest to TARGET_H; falls back to
    the tallest portrait file; returns None if no portrait file exists.
    """
    files = video.get("video_files") or []
    portrait = []
    for vf in files:
        w = vf.get("width") or 0
        h = vf.get("height") or 0
        link = vf.get("link")
        if not link or w <= 0 or h <= 0:
            continue
        if h > w:  # portrait / vertical only
            portrait.append(vf)
    if not portrait:
        return None
    # Closest height to target, then tallest as tie-breaker.
    portrait.sort(key=lambda vf: (abs((vf.get("height") or 0) - TARGET_H),
                                  -(vf.get("height") or 0)))
    return portrait[0]


def fetch_intro_clip(niche: str, out_dir, mock: bool = False,
                     fixture_path=None, timeout: int = 20):
    """Download one vertical b-roll clip for the niche; return its path or None.

    Args:
        niche: catalog niche (electronics|smart-home|sport|gadgets).
        out_dir: directory where the clip is saved (must be gitignored, e.g. out/).
        mock: when True, performs NO network call. Returns fixture_path if it
              points to an existing file, else None. Used by offline tests.
        fixture_path: optional local clip to return in mock mode.
        timeout: per-request timeout (seconds).

    Returns:
        Path to the downloaded clip, or None on any failure / missing key.
        NEVER raises.
    """
    try:
        out_dir = Path(out_dir)
        # Mock / offline mode: never touch the network.
        if mock:
            if fixture_path:
                fp = Path(fixture_path)
                return fp if fp.is_file() else None
            return None

        api_key = os.getenv("PEXELS_API_KEY")
        if not api_key:
            print("[info] PEXELS_API_KEY not set; using animated intro fallback.")
            return None

        import requests  # local import: stdlib-only consumers stay clean

        query = query_for_niche(niche)
        resp = requests.get(
            PEXELS_VIDEO_SEARCH,
            headers={"Authorization": api_key},
            params={
                "query": query,
                "orientation": "portrait",
                "per_page": 5,
                "size": "medium",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("videos") or []
        chosen_file = None
        chosen_id = None
        for video in videos:
            vf = _pick_video_file(video)
            if vf:
                chosen_file = vf
                chosen_id = video.get("id", "clip")
                break
        if not chosen_file:
            print(f"[info] Pexels returned no usable vertical clip for '{query}'.")
            return None

        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"intro-{niche}-{chosen_id}.mp4"
        with requests.get(chosen_file["link"], stream=True, timeout=timeout) as dl:
            dl.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
        if dest.is_file() and dest.stat().st_size > 0:
            print(f"[ok] intro clip downloaded: {dest.name} "
                  f"({dest.stat().st_size // 1024} KB, query='{query}')")
            return dest
        return None
    except Exception as exc:  # degrade silently, never break the pipeline
        print(f"[warn] intro clip fetch failed ({exc}); using animated fallback.")
        return None
