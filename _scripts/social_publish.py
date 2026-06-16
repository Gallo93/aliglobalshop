"""Social publishing (Fase 2): DRY_RUN by default, live behind SOCIAL_LIVE=1.

In DRY_RUN each publisher only logs what it WOULD post (platform, file, caption,
target link) so the whole flow is testable without any account. The live branch
(SOCIAL_LIVE=1 + the platform env present) is implemented for Facebook and
Instagram via the Meta Graph API; TikTok and X stay NotImplementedError with a
clear message. Live never triggers unless explicitly opted in.

Live uploads need the video reachable as a PUBLIC URL (Cloudinary), not a local
file: IG Reels and the FB video API both fetch the bytes themselves. Pass it on
the job as "video_url"; if missing in live mode we raise a clear error.

Env vars (set as GitHub Actions secrets when accounts are linked; NEVER commit):
    SOCIAL_LIVE=1              master opt-in switch (anything else = DRY_RUN)
    META_PAGE_ACCESS_TOKEN     Facebook Page + Instagram Graph API token
    META_IG_USER_ID            Instagram business account id (Reels)
    META_FB_PAGE_ID            Facebook page id (video publish)
    TIKTOK_ACCESS_TOKEN        TikTok Content Posting API token (not implemented)
    X_BEARER_TOKEN             X (Twitter) API token (not implemented)
"""
import os
import time
from pathlib import Path

# Single switch. Defaults to DRY_RUN; only a real token + explicit opt-in
# (SOCIAL_LIVE=1) flips this.
DRY_RUN = not (os.getenv("SOCIAL_LIVE") == "1")

GRAPH_API = "https://graph.facebook.com/v21.0"

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


def _require_env(platform):
    missing = [e for e in PLATFORM_ENV.get(platform, []) if not os.getenv(e)]
    if missing:
        raise RuntimeError(
            f"{platform}: missing env {missing}; cannot publish live. "
            f"Set them as secrets (SOCIAL_LIVE=1 enables the live branch).")


def _require_video_url(platform, video_url):
    if not video_url:
        raise RuntimeError(
            f"{platform}: live publish needs a public 'video_url' (Cloudinary). "
            "Upload the rendered MP4 and pass video_url on the job.")


# --- live publishers (Meta Graph API) ---------------------------------------

def _publish_facebook_live(video_url, caption, link=None):
    """Publish a video to the Facebook Page. The link is included in-post via
    the post description (FB allows a clickable link in the body)."""
    import requests
    _require_env("facebook")
    _require_video_url("facebook", video_url)
    page_id = os.getenv("META_FB_PAGE_ID")
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    description = caption or ""
    if link and link not in description:
        description = f"{description}\n\n{link}".strip()
    resp = requests.post(
        f"{GRAPH_API}/{page_id}/videos",
        data={"file_url": video_url, "description": description,
              "access_token": token},
        timeout=120,
    )
    body = resp.json()
    if resp.status_code >= 400 or "error" in body:
        raise RuntimeError(f"facebook publish failed: {body}")
    return {
        "platform": "facebook",
        "dry_run": False,
        "published": True,
        "id": body.get("id"),
        "video_url": video_url,
        "link": link,
    }


def _publish_instagram_live(video_url, caption, link=None):
    """Publish an Instagram Reel: create a media container (REELS) pointing at
    the public video_url, poll until processed, then publish. IG captions cannot
    carry a clickable link, so the link stays in the bio (not appended here)."""
    import requests
    _require_env("instagram")
    _require_video_url("instagram", video_url)
    ig_user = os.getenv("META_IG_USER_ID")
    token = os.getenv("META_PAGE_ACCESS_TOKEN")

    create = requests.post(
        f"{GRAPH_API}/{ig_user}/media",
        data={"media_type": "REELS", "video_url": video_url,
              "caption": caption or "", "access_token": token},
        timeout=120,
    )
    cbody = create.json()
    if create.status_code >= 400 or "error" in cbody:
        raise RuntimeError(f"instagram container failed: {cbody}")
    creation_id = cbody.get("id")
    if not creation_id:
        raise RuntimeError(f"instagram container missing id: {cbody}")

    # Reels are processed asynchronously; poll status before publishing.
    for _ in range(20):
        status = requests.get(
            f"{GRAPH_API}/{creation_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        ).json()
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"instagram media processing error: {status}")
        time.sleep(6)
    else:
        raise RuntimeError("instagram media not ready after polling timeout")

    publish = requests.post(
        f"{GRAPH_API}/{ig_user}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=120,
    )
    pbody = publish.json()
    if publish.status_code >= 400 or "error" in pbody:
        raise RuntimeError(f"instagram publish failed: {pbody}")
    return {
        "platform": "instagram",
        "dry_run": False,
        "published": True,
        "id": pbody.get("id"),
        "video_url": video_url,
        "link": "(in bio)",
    }


_LIVE_PUBLISHERS = {
    "facebook": _publish_facebook_live,
    "instagram": _publish_instagram_live,
}


def _publish(platform, video_path, caption, link=None, dry_run=True,
             video_url=None):
    if dry_run or DRY_RUN:
        return _log(platform, video_path, caption, link)
    live = _LIVE_PUBLISHERS.get(platform)
    if live:
        return live(video_url, caption, link)
    # TikTok / X: env documented, live not implemented yet.
    _require_env(platform)
    raise NotImplementedError(
        f"Live publishing to {platform} is not implemented yet "
        "(Facebook and Instagram are; TikTok and X are pending).")


def publish_facebook(video_path, caption, link=None, dry_run=True, video_url=None):
    return _publish("facebook", video_path, caption, link, dry_run, video_url)


def publish_instagram(video_path, caption, link=None, dry_run=True, video_url=None):
    return _publish("instagram", video_path, caption, link, dry_run, video_url)


def publish_tiktok(video_path, caption, link=None, dry_run=True, video_url=None):
    return _publish("tiktok", video_path, caption, link, dry_run, video_url)


def publish_x(video_path, caption, link=None, dry_run=True, video_url=None):
    return _publish("x", video_path, caption, link, dry_run, video_url)


PUBLISHERS = {
    "facebook": publish_facebook,
    "instagram": publish_instagram,
    "tiktok": publish_tiktok,
    "x": publish_x,
}


def publish_all(video_path, captions: dict, link=None, platforms=None,
                dry_run=True, video_url=None):
    """Publish to each platform using its own caption.

    captions: {platform: caption_text}. Returns list of result dicts. In live
    mode (dry_run False and SOCIAL_LIVE=1) IG/FB need a public video_url.
    """
    platforms = platforms or list(PUBLISHERS.keys())
    results = []
    for p in platforms:
        fn = PUBLISHERS.get(p)
        if not fn:
            print(f"[warn] unknown platform '{p}', skipping")
            continue
        results.append(fn(video_path, captions.get(p, ""), link, dry_run,
                          video_url))
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
