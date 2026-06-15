"""Social publishing stubs (Fase 1, DRY_RUN only).

No network calls happen in this phase. Each publisher logs exactly what it
WOULD post (platform, file, caption, target link) so the flow is testable
without any account connected. Real tokens will be read from env later; their
names are documented below and must NEVER be committed.

Future env vars (set as GitHub Actions secrets when accounts are linked):
    META_PAGE_ACCESS_TOKEN     Facebook Page + Instagram Graph API token
    META_IG_USER_ID            Instagram business account id
    META_FB_PAGE_ID            Facebook page id
    TIKTOK_ACCESS_TOKEN        TikTok Content Posting API token
    X_BEARER_TOKEN             X (Twitter) API token
"""
import os
from pathlib import Path

# Single switch. Defaults to DRY_RUN; only a real token + explicit opt-in
# (SOCIAL_LIVE=1) should ever flip this, which Fase 1 never does.
DRY_RUN = not (os.getenv("SOCIAL_LIVE") == "1")

PLATFORM_ENV = {
    "facebook": ["META_PAGE_ACCESS_TOKEN", "META_FB_PAGE_ID"],
    "instagram": ["META_PAGE_ACCESS_TOKEN", "META_IG_USER_ID"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN"],
    "x": ["X_BEARER_TOKEN"],
}


def _log(platform, video_path, caption, link):
    head = (caption or "").strip().splitlines()
    preview = head[0] if head else ""
    print(f"[DRY_RUN][{platform}] would publish")
    print(f"    file:    {video_path}")
    print(f"    link:    {link or '(in caption / bio)'}")
    print(f"    caption: {preview} ...")
    return {
        "platform": platform,
        "dry_run": True,
        "video": str(video_path),
        "link": link,
        "caption_chars": len(caption or ""),
        "published": False,
    }


def _publish(platform, video_path, caption, link=None, dry_run=True):
    if dry_run or DRY_RUN:
        return _log(platform, video_path, caption, link)
    # Live path intentionally not implemented in Fase 1.
    missing = [e for e in PLATFORM_ENV.get(platform, []) if not os.getenv(e)]
    if missing:
        raise RuntimeError(
            f"{platform}: missing env {missing}; cannot publish live")
    raise NotImplementedError(
        f"Live publishing to {platform} is not enabled in Fase 1")


def publish_facebook(video_path, caption, link=None, dry_run=True):
    return _publish("facebook", video_path, caption, link, dry_run)


def publish_instagram(video_path, caption, link=None, dry_run=True):
    return _publish("instagram", video_path, caption, link, dry_run)


def publish_tiktok(video_path, caption, link=None, dry_run=True):
    return _publish("tiktok", video_path, caption, link, dry_run)


def publish_x(video_path, caption, link=None, dry_run=True):
    return _publish("x", video_path, caption, link, dry_run)


PUBLISHERS = {
    "facebook": publish_facebook,
    "instagram": publish_instagram,
    "tiktok": publish_tiktok,
    "x": publish_x,
}


def publish_all(video_path, captions: dict, link=None, platforms=None,
                dry_run=True):
    """Publish to each platform using its own caption.

    captions: {platform: caption_text}. Returns list of result dicts.
    """
    platforms = platforms or list(PUBLISHERS.keys())
    results = []
    for p in platforms:
        fn = PUBLISHERS.get(p)
        if not fn:
            print(f"[warn] unknown platform '{p}', skipping")
            continue
        results.append(fn(video_path, captions.get(p, ""), link, dry_run))
    return results


if __name__ == "__main__":
    # Tiny self-demo without any real file/token.
    demo = publish_all(
        Path("out/social/demo-en.mp4"),
        {"facebook": "#ad ...", "instagram": "#ad ...",
         "tiktok": "#ad ...", "x": "#ad ..."},
        link="https://aliglobalshop.net/en/sport/demo/",
        dry_run=True,
    )
    print(f"[done] {len(demo)} platforms simulated (DRY_RUN).")
