"""Telegram approval flow for social videos (Fase 1, DRY_RUN-safe).

Sends the generated video (or a thumbnail) plus its caption to the admin chat
with inline buttons Approva / Scarta / Rigenera. On Approva it calls the
publish stubs (which only log in DRY_RUN). Without a token it runs in mock mode:
no network, it just logs the exact payload it would send, so the whole flow is
testable with zero accounts.

Env (set as secrets when the bot is created, never committed):
    SOCIAL_BOT_TOKEN        Telegram bot token
    SOCIAL_ADMIN_CHAT_ID    chat id allowed to approve

Usage:
    # build a preview payload for an already-generated video (mock or live send)
    python _scripts/social_bot.py --slug <slug> --lang it
    # poll for button presses (only when a real token is set)
    python _scripts/social_bot.py --serve
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from social_common import (  # noqa: E402
    BASE_DIR,
    SITE_URL_DEFAULT,
    load_config,
    pick_product,
    product_url,
)
from social_caption import build_all_captions, PLATFORMS  # noqa: E402
import social_publish  # noqa: E402

OUT_DIR = BASE_DIR / "out" / "social"
ARCHIVE_DIR = OUT_DIR / "_discarded"
API_BASE = "https://api.telegram.org/bot{token}/{method}"

BOT_TOKEN = os.getenv("SOCIAL_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("SOCIAL_ADMIN_CHAT_ID", "")
MOCK = not (BOT_TOKEN and ADMIN_CHAT_ID)

# Inline keyboard. callback_data stays well under Telegram's 64-byte limit by
# carrying only an action + short job id (the job file holds the rest).
ACTIONS = ("approve", "discard", "regen")
_BTN_LABELS = {
    "approve": "Approva",
    "discard": "Scarta",
    "regen": "Rigenera",
}


def _keyboard(job_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": _BTN_LABELS["approve"], "callback_data": f"approve:{job_id}"},
        {"text": _BTN_LABELS["discard"], "callback_data": f"discard:{job_id}"},
        {"text": _BTN_LABELS["regen"], "callback_data": f"regen:{job_id}"},
    ]]}


def _job_path(job_id: str) -> Path:
    return OUT_DIR / f"{job_id}.job.json"


def build_job(slug: str | None, lang: str) -> dict:
    """Assemble the approval job metadata for a product/language."""
    config = load_config()
    site_url = config.get("site_url", SITE_URL_DEFAULT)
    product = pick_product(lang, slug)
    if not product:
        raise SystemExit(f"[error] no product (lang={lang}, slug={slug})")
    real_slug = product.get("slug")
    job_id = f"{real_slug}-{lang}"
    captions = build_all_captions(product, lang, config, site_url)
    job = {
        "job_id": job_id,
        "slug": real_slug,
        "lang": lang,
        "title": product.get("title", ""),
        "platforms": PLATFORMS,
        "video": str(OUT_DIR / f"{job_id}.mp4"),
        "caption_file": str(OUT_DIR / f"{job_id}.caption.txt"),
        "link": product_url(product, lang, site_url),
        "captions": captions,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_job_path(job_id), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    return job


def _tg(method: str, **payload):
    """Call Telegram API, or log the payload in mock mode (no network)."""
    if MOCK:
        print(f"[MOCK][telegram.{method}] {json.dumps(payload, ensure_ascii=False)[:600]}")
        return {"ok": True, "mock": True}
    try:
        import requests
        url = API_BASE.format(token=BOT_TOKEN, method=method)
        resp = requests.post(url, json=payload, timeout=30)
        return resp.json()
    except Exception as exc:
        print(f"[warn] telegram {method} failed: {exc}")
        return {"ok": False, "error": str(exc)}


def send_for_approval(job: dict) -> dict:
    """Send the video preview + caption + inline buttons to the admin."""
    lang = job["lang"]
    caption = job["captions"].get("instagram", "")
    text = (
        f"Anteprima video social\n"
        f"Prodotto: {job['title'][:80]}\n"
        f"Lingua: {lang} | Piattaforme: {', '.join(job['platforms'])}\n"
        f"Link: {job['link']}\n\n"
        f"{caption}"
    )
    kb = _keyboard(job["job_id"])
    video_path = job["video"]

    if MOCK:
        # In mock mode we don't upload bytes; we log the would-be send.
        print(f"[MOCK] sendVideo chat={ADMIN_CHAT_ID or '<unset>'} "
              f"video={video_path} buttons={[b['text'] for b in kb['inline_keyboard'][0]]}")
        return _tg("sendVideo", chat_id=ADMIN_CHAT_ID, caption=text[:1024],
                   reply_markup=kb, video=f"file://{video_path}")

    # Live: upload the file if present, else fall back to a text message.
    if Path(video_path).is_file():
        try:
            import requests
            url = API_BASE.format(token=BOT_TOKEN, method="sendVideo")
            with open(video_path, "rb") as fh:
                resp = requests.post(
                    url,
                    data={"chat_id": ADMIN_CHAT_ID, "caption": text[:1024],
                          "reply_markup": json.dumps(kb)},
                    files={"video": fh}, timeout=120)
            return resp.json()
        except Exception as exc:
            print(f"[warn] sendVideo failed ({exc}); sending text instead")
    return _tg("sendMessage", chat_id=ADMIN_CHAT_ID, text=text[:4096],
               reply_markup=kb)


def _load_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not path.is_file():
        print(f"[warn] job not found: {job_id}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def handle_callback(callback_data: str) -> dict:
    """Route an inline-button press. Returns a result dict."""
    try:
        action, job_id = callback_data.split(":", 1)
    except ValueError:
        return {"ok": False, "error": "bad callback_data"}
    if action not in ACTIONS:
        return {"ok": False, "error": f"unknown action {action}"}
    job = _load_job(job_id)
    if not job:
        return {"ok": False, "error": "job missing"}

    if action == "approve":
        results = social_publish.publish_all(
            job["video"], job["captions"], link=job["link"],
            platforms=job["platforms"], dry_run=True)
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text=f"Approvato: {job_id} (DRY_RUN, {len(results)} piattaforme simulate).")
        return {"ok": True, "action": "approve", "results": results}

    if action == "discard":
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for key in ("video", "caption_file"):
            src = Path(job[key])
            if src.is_file():
                try:
                    src.replace(ARCHIVE_DIR / src.name)
                except OSError:
                    pass
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID, text=f"Scartato: {job_id}.")
        return {"ok": True, "action": "discard"}

    # regen: Fase 1 stub. Re-running the generator is wired in Fase 2.
    _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
        text=f"Rigenerazione richiesta per {job_id} (stub Fase 1).")
    return {"ok": True, "action": "regen", "stub": True}


def serve(poll_interval: int = 2):
    """Long-poll for button presses. Live mode only."""
    if MOCK:
        print("[error] --serve needs SOCIAL_BOT_TOKEN + SOCIAL_ADMIN_CHAT_ID. "
              "Set them to run the live approval loop.", file=sys.stderr)
        return
    print("[info] polling Telegram for approvals (Ctrl+C to stop)...")
    offset = 0
    while True:
        resp = _tg("getUpdates", offset=offset, timeout=25)
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            cq = upd.get("callback_query")
            if not cq:
                continue
            data = cq.get("data", "")
            _tg("answerCallbackQuery", callback_query_id=cq["id"])
            print(f"[info] callback: {data}")
            print(json.dumps(handle_callback(data), ensure_ascii=False))
        time.sleep(poll_interval)


def main():
    ap = argparse.ArgumentParser(description="Telegram approval flow for social videos (DRY_RUN-safe).")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--serve", action="store_true", help="poll for button presses (live only)")
    ap.add_argument("--simulate", choices=ACTIONS, help="simulate a button press for the built job")
    args = ap.parse_args()

    if args.serve:
        serve()
        return

    print(f"[info] mode: {'MOCK (no token)' if MOCK else 'LIVE'}")
    job = build_job(args.slug, args.lang)
    print(f"[ok] job built: {job['job_id']}")
    send_for_approval(job)
    if args.simulate:
        print(f"[info] simulating '{args.simulate}' press...")
        result = handle_callback(f"{args.simulate}:{job['job_id']}")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
