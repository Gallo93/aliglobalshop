"""Telegram approval flow for social videos (Fase 2, DRY_RUN-safe).

Sends the generated reel (or a thumbnail) plus its caption to the admin chat
with five inline buttons, matching the ToniGuy bot:
    Pubblica ora | Programma | Modifica | Rigenera | Scarta
Without a token it runs in mock mode: no network, it just logs the exact
payload it would send, so the whole flow is testable with zero accounts.

Publishing respects social_publish.DRY_RUN: in DRY_RUN "Pubblica ora" only
simulates; with SOCIAL_LIVE=1 (and the platform env) it publishes for real.

Env (set as secrets when the bot is created, never committed):
    SOCIAL_BOT_TOKEN        Telegram bot token
    SOCIAL_ADMIN_CHAT_ID    chat id allowed to approve
    SOCIAL_LIVE=1           opt-in to real publishing (see social_publish)

Usage:
    # build a preview payload for an already-generated reel (mock or live send)
    python _scripts/social_bot.py --slug <slug> --lang it
    # poll for button presses (only when a real token is set)
    python _scripts/social_bot.py --serve
    # process the scheduled queue (cron): publish jobs whose time has come
    python _scripts/social_bot.py --run-scheduled
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
SCHEDULED_DIR = OUT_DIR / "_scheduled"
API_BASE = "https://api.telegram.org/bot{token}/{method}"
ROME = ZoneInfo("Europe/Rome")
SCHEDULE_FMT = "%Y-%m-%d %H:%M"

BOT_TOKEN = os.getenv("SOCIAL_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("SOCIAL_ADMIN_CHAT_ID", "")
MOCK = not (BOT_TOKEN and ADMIN_CHAT_ID)

# Inline keyboard. callback_data stays well under Telegram's 64-byte limit by
# carrying only an action + short job id (the job file holds the rest).
ACTIONS = ("approve", "schedule", "edit", "regen", "discard")
_BTN_LABELS = {
    "approve": "Pubblica ora",
    "schedule": "Programma",
    "edit": "Modifica",
    "regen": "Rigenera",
    "discard": "Scarta",
}


def _keyboard(job_id: str) -> dict:
    row = [{"text": _BTN_LABELS[a], "callback_data": f"{a}:{job_id}"}
           for a in ACTIONS]
    return {"inline_keyboard": [row]}


def _job_path(job_id: str) -> Path:
    return OUT_DIR / f"{job_id}.job.json"


def _save_job(job: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_job_path(job["job_id"]), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)


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
        # Public URL (Cloudinary) needed for live IG/FB; filled by the pipeline.
        "video_url": product.get("video_url") or None,
        "caption_file": str(OUT_DIR / f"{job_id}.caption.txt"),
        "link": product_url(product, lang, site_url),
        "captions": captions,
        "scheduled_at": None,
    }
    _save_job(job)
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


def _publish_job(job: dict) -> list:
    """Publish a job through social_publish (DRY_RUN unless SOCIAL_LIVE=1)."""
    return social_publish.publish_all(
        job["video"], job["captions"], link=job["link"],
        platforms=job["platforms"], dry_run=social_publish.DRY_RUN,
        video_url=job.get("video_url"))


def _set_caption_all(job: dict, new_caption: str) -> None:
    """Replace the caption on every platform and rewrite the caption file."""
    new_caption = new_caption.replace("—", "-").replace("–", "-")
    for platform in list(job["captions"].keys()):
        job["captions"][platform] = new_caption
    _save_job(job)
    cap_path = Path(job["caption_file"])
    try:
        cap_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cap_path, "w", encoding="utf-8") as f:
            for platform, text in job["captions"].items():
                f.write(f"===== {platform.upper()} =====\n{text}\n\n")
    except OSError as exc:
        print(f"[warn] caption file rewrite failed: {exc}")


def _regen(job: dict) -> dict:
    """Rebuild props + caption for the job, then dispatch the Remotion render.

    Re-runs generate_social_video.py for slug/lang (refreshes out/social props +
    caption), then triggers the render workflow via `gh workflow run`. If gh is
    unavailable (e.g. local mock), it logs the action without failing.
    """
    import shutil
    import subprocess
    slug, lang = job["slug"], job["lang"]
    gen = BASE_DIR / "_scripts" / "generate_social_video.py"
    try:
        subprocess.run([sys.executable, str(gen), "--slug", slug,
                        "--lang", lang, "--no-video"],
                       cwd=str(BASE_DIR), check=False)
    except Exception as exc:
        print(f"[warn] regen inputs build failed: {exc}")

    run_url = None
    if shutil.which("gh"):
        try:
            subprocess.run(
                ["gh", "workflow", "run", "social_video.yml",
                 "-f", f"slug={slug}", "-f", f"lang={lang}"],
                cwd=str(BASE_DIR), check=False)
            run_url = f"workflow social_video.yml dispatched (slug={slug}, lang={lang})"
        except Exception as exc:
            print(f"[warn] gh workflow run failed: {exc}")
    else:
        print(f"[info] gh not available; would dispatch render for {slug}/{lang}")
    return {"ok": True, "action": "regen", "run": run_url}


def handle_callback(callback_data: str, pending: dict | None = None,
                    chat_id=None) -> dict:
    """Route an inline-button press. Returns a result dict.

    `pending` is the per-chat state map (chat_id -> {"mode", "job_id"}); for
    schedule/edit we record that the next text message belongs to this job.
    """
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
        results = _publish_job(job)
        mode = "DRY_RUN" if social_publish.DRY_RUN else "LIVE"
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text=f"Pubblicato: {job_id} ({mode}, {len(results)} piattaforme).")
        return {"ok": True, "action": "approve", "results": results}

    if action == "schedule":
        if pending is not None and chat_id is not None:
            pending[chat_id] = {"mode": "schedule", "job_id": job_id}
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text=("Inviami data e ora di pubblicazione nel formato "
                  "AAAA-MM-GG HH:MM (fuso Europe/Rome)."))
        return {"ok": True, "action": "schedule", "awaiting": "datetime"}

    if action == "edit":
        if pending is not None and chat_id is not None:
            pending[chat_id] = {"mode": "edit", "job_id": job_id}
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text="Inviami la nuova didascalia: sostituira quella attuale.")
        return {"ok": True, "action": "edit", "awaiting": "caption"}

    if action == "regen":
        result = _regen(job)
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text=f"Rigenerazione avviata per {job_id}. Render in corso.")
        return result

    # discard
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for key in ("video", "caption_file"):
        src = Path(job[key])
        if src.is_file():
            try:
                src.replace(ARCHIVE_DIR / src.name)
            except OSError:
                pass
    sched = SCHEDULED_DIR / f"{job_id}.job.json"
    if sched.is_file():
        try:
            sched.unlink()
        except OSError:
            pass
    _tg("sendMessage", chat_id=ADMIN_CHAT_ID, text=f"Scartato: {job_id}.")
    return {"ok": True, "action": "discard"}


def _apply_schedule(job_id: str, text: str) -> dict:
    """Parse a 'YYYY-MM-DD HH:MM' (Europe/Rome) string and queue the job."""
    job = _load_job(job_id)
    if not job:
        return {"ok": False, "error": "job missing"}
    try:
        naive = datetime.strptime(text.strip(), SCHEDULE_FMT)
    except ValueError:
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text="Formato non valido. Usa AAAA-MM-GG HH:MM (es. 2026-06-20 18:30).")
        return {"ok": False, "error": "bad datetime"}
    when = naive.replace(tzinfo=ROME)
    job["scheduled_at"] = when.isoformat()
    _save_job(job)
    SCHEDULED_DIR.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULED_DIR / f"{job_id}.job.json", "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
        text=f"Programmato: {job_id} per {when.strftime(SCHEDULE_FMT)} (Europe/Rome).")
    return {"ok": True, "action": "schedule", "scheduled_at": job["scheduled_at"]}


def _apply_edit(job_id: str, text: str) -> dict:
    job = _load_job(job_id)
    if not job:
        return {"ok": False, "error": "job missing"}
    _set_caption_all(job, text)
    send_for_approval(job)
    return {"ok": True, "action": "edit"}


def run_scheduled() -> list:
    """Publish queued jobs whose scheduled_at <= now (Europe/Rome), then drop
    them from the queue. Respects social_publish.DRY_RUN."""
    results = []
    if not SCHEDULED_DIR.is_dir():
        print("[info] no scheduled queue.")
        return results
    now = datetime.now(ROME)
    for jf in sorted(SCHEDULED_DIR.glob("*.job.json")):
        try:
            with open(jf, encoding="utf-8") as f:
                job = json.load(f)
        except (OSError, ValueError):
            continue
        sched = job.get("scheduled_at")
        if not sched:
            continue
        try:
            when = datetime.fromisoformat(sched)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=ROME)
        if when > now:
            continue
        print(f"[info] publishing scheduled job {job['job_id']} (due {sched})")
        published = _publish_job(job)
        results.append({"job_id": job["job_id"], "results": published})
        _tg("sendMessage", chat_id=ADMIN_CHAT_ID,
            text=f"Pubblicato (programmato): {job['job_id']}.")
        try:
            jf.unlink()
        except OSError:
            pass
    if not results:
        print("[info] no scheduled job due yet.")
    return results


def serve(poll_interval: int = 2):
    """Long-poll for button presses and follow-up text. Live mode only."""
    if MOCK:
        print("[error] --serve needs SOCIAL_BOT_TOKEN + SOCIAL_ADMIN_CHAT_ID. "
              "Set them to run the live approval loop.", file=sys.stderr)
        return
    print("[info] polling Telegram for approvals (Ctrl+C to stop)...")
    offset = 0
    pending: dict = {}  # chat_id -> {"mode": "schedule"|"edit", "job_id": ...}
    while True:
        resp = _tg("getUpdates", offset=offset, timeout=25)
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            cq = upd.get("callback_query")
            if cq:
                data = cq.get("data", "")
                chat = cq.get("message", {}).get("chat", {}).get("id")
                _tg("answerCallbackQuery", callback_query_id=cq["id"])
                print(f"[info] callback: {data}")
                print(json.dumps(
                    handle_callback(data, pending=pending, chat_id=chat),
                    ensure_ascii=False))
                continue
            msg = upd.get("message")
            if not msg:
                continue
            chat = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            state = pending.pop(chat, None)
            if not state or not text:
                continue
            if state["mode"] == "schedule":
                print(json.dumps(_apply_schedule(state["job_id"], text),
                                 ensure_ascii=False))
            elif state["mode"] == "edit":
                print(json.dumps(_apply_edit(state["job_id"], text),
                                 ensure_ascii=False))
        time.sleep(poll_interval)


def _simulate(action: str, job: dict):
    """Drive an action without Telegram, covering the follow-up text steps."""
    pending: dict = {}
    fake_chat = "sim"
    result = handle_callback(f"{action}:{job['job_id']}", pending=pending,
                             chat_id=fake_chat)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if action == "schedule":
        print("[info] simulating scheduled datetime input...")
        when = datetime.now(ROME).strftime(SCHEDULE_FMT)
        print(json.dumps(_apply_schedule(job["job_id"], when),
                         ensure_ascii=False, indent=2))
    elif action == "edit":
        print("[info] simulating new caption input...")
        print(json.dumps(_apply_edit(job["job_id"], "Nuova didascalia di test"),
                         ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Telegram approval flow for social videos (DRY_RUN-safe).")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--serve", action="store_true", help="poll for button presses (live only)")
    ap.add_argument("--run-scheduled", action="store_true",
                    help="publish queued jobs whose time has come (cron)")
    ap.add_argument("--simulate", choices=ACTIONS, help="simulate a button press for the built job")
    args = ap.parse_args()

    if args.run_scheduled:
        run_scheduled()
        return

    if args.serve:
        serve()
        return

    print(f"[info] mode: {'MOCK (no token)' if MOCK else 'LIVE'}")
    job = build_job(args.slug, args.lang)
    print(f"[ok] job built: {job['job_id']}")
    send_for_approval(job)
    if args.simulate:
        print(f"[info] simulating '{args.simulate}' press...")
        _simulate(args.simulate, job)


if __name__ == "__main__":
    main()
