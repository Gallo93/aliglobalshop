# Video social - reel animati (DRY_RUN)

Pipeline per generare reel verticali "Product Spotlight" dai prodotti del
catalogo: ora **reel animati veri** (motion graphics via Remotion), con caption
compliant e approvazione via Telegram. Default in DRY_RUN: nessuna pubblicazione
reale, nessun token richiesto. La pubblicazione vera (Facebook + Instagram)
scatta solo con `SOCIAL_LIVE=1` e i secret della piattaforma presenti.

## Architettura

- **Dati**: `generate_social_video.py` (engine `remotion`, default) scrive
  `out/social/<slug>-<lang>.props.json` con i dati del prodotto + prezzo gia
  localizzato (stesso `format_price` di build.py) + la caption per piattaforma.
- **Render**: il progetto **Remotion** in `social/remotion/` legge quei props e
  produce l'MP4 9:16 animato (intro, card ken-burns, prezzo spring, badge sconto,
  feature in stagger, CTA, sfondo in movimento, disclosure sempre visibile).
- **Fallback**: engine `ffmpeg` (Pillow + ffmpeg) resta come render statico
  legacy documentato, senza dipendenze Node.

## File

| File | Ruolo |
|------|-------|
| `social_common.py` | helper condivisi: catalogo, prezzo localizzato (come build.py), disclosure |
| `social_caption.py` | caption compliant per lingua + piattaforma |
| `generate_social_video.py` | scrive props per Remotion (+ caption); engine `ffmpeg` opzionale |
| `social/remotion/` | progetto Remotion (composizione `ProductSpotlight`, font bundlati) |
| `social_publish.py` | pubblicazione: DRY_RUN logga; live FB/IG via Meta Graph API dietro `SOCIAL_LIVE=1` |
| `social_bot.py` | approvazione Telegram (anteprima + 5 bottoni, schedule, edit, regen) |

## Uso locale

```bash
pip install requests
# 1) genera props (+ caption). Se Node + node_modules ci sono, renderizza anche
python _scripts/generate_social_video.py --lang it
python _scripts/generate_social_video.py --lang en --slug <slug>
python _scripts/generate_social_video.py --lang de --no-video   # solo caption+props

# 2) render esplicito con Remotion (se non gia fatto sopra)
cd social/remotion && npm ci
npx remotion render ProductSpotlight \
  ../../out/social/<slug>-<lang>.mp4 \
  --props=../../out/social/<slug>-<lang>.props.json

# fallback statico senza Node
python _scripts/generate_social_video.py --lang it --engine ffmpeg
```

Output in `out/social/` (NON committato): `<slug>-<lang>.props.json`,
`<slug>-<lang>.mp4`, `<slug>-<lang>.caption.txt` (una caption per piattaforma:
facebook/instagram/tiktok/x), `<slug>-<lang>.job.json` (metadati approvazione).

## Approvazione Telegram

```bash
python _scripts/social_bot.py --lang it
python _scripts/social_bot.py --lang it --simulate approve     # simula bottone
python _scripts/social_bot.py --lang it --simulate schedule    # simula programmazione
python _scripts/social_bot.py --lang it --simulate edit        # simula modifica caption
SOCIAL_BOT_TOKEN=... SOCIAL_ADMIN_CHAT_ID=... python _scripts/social_bot.py --serve
python _scripts/social_bot.py --run-scheduled                  # coda programmata (cron)
```

Cinque bottoni (a parita col bot ToniGuy):

- **Pubblica ora** -> chiama `social_publish.publish_all` rispettando DRY_RUN.
  In DRY_RUN logga; con `SOCIAL_LIVE=1` pubblica davvero su FB/IG.
- **Programma** -> il bot chiede data/ora (`AAAA-MM-GG HH:MM`, fuso Europe/Rome);
  il job viene messo in coda in `out/social/_scheduled/`.
- **Modifica** -> il bot chiede la nuova didascalia, la sostituisce su tutte le
  piattaforme, riscrive il file caption e rimanda l'anteprima.
- **Rigenera** -> ricostruisce props+caption e fa il dispatch del render
  (`gh workflow run social_video.yml -f slug=... -f lang=...`). Senza `gh`
  (es. mock) logga l'azione senza fallire.
- **Scarta** -> archivia video+caption in `out/social/_discarded/` e rimuove dalla coda.

## Pubblicazione programmata

`python _scripts/social_bot.py --run-scheduled` scorre `out/social/_scheduled/`
e pubblica i job con `scheduled_at <= adesso` (Europe/Rome), poi li rimuove.
Lo lancia il workflow `social_scheduled.yml` (cron ogni 15 min). **Attenzione**:
`out/social/` e' gitignored, quindi la coda NON e' persistita nel repo. Per la
programmazione reale va persistita (artifact/cache/host con stato).

## Workflow GitHub Actions

- `social_video.yml` -> `workflow_dispatch` (input: `lang`, `slug`). Renderizza
  un reel e lo carica come **artifact**. Nessun segreto, nessuna pubblicazione.
- `social_scheduled.yml` -> cron `*/15` + dispatch manuale. Lancia
  `--run-scheduled`. Secret passati come env (DRY_RUN se `SOCIAL_LIVE` non e' `1`).

## Pubblicazione reale (live)

Solo con `SOCIAL_LIVE=1` E i secret della piattaforma presenti:

- **Facebook**: `POST {page_id}/videos` con `file_url` (URL pubblico del video,
  es. Cloudinary) + `description` (caption con il link in-post).
- **Instagram (Reels)**: crea container `REELS` con `video_url` + `caption`,
  poll dello stato, poi `media_publish`. Il link va in bio (IG non ha link
  cliccabili in caption).
- **TikTok / X**: `NotImplementedError` con messaggio chiaro (env documentati).

Il video per IG/FB va servito via **URL pubblico**: il campo `video_url` del job
(in DRY_RUN puo' mancare). In live, se manca, errore chiaro.

## Compliance

- Disclosure SEMPRE visibile nel reel (overlay #ad/#adv... + "link affiliato")
  e in apertura di ogni caption.
- CTA cliccabile per piattaforma nella CAPTION: IG/TikTok "link in bio"; FB/X
  link diretto. Il reel e' uno solo multipiattaforma, quindi la CTA SOVRAIMPRESSA
  e' neutra ("Scoprilo ora" / "Shop now" ...) e vera ovunque.
- Niente musica (richiede licenza commerciale): reel silenzioso.
- Niente em-dash nei testi visibili (regola sito).

## NOTA LICENZA REMOTION (verificare prima del go-live commerciale)

Remotion puo' richiedere la **Company License** a pagamento per uso aziendale
sopra certe soglie. Essendo un sito di affiliazione, **prima di pubblicare reel
reali** va verificata la licenza per il nostro caso (e, se dovuta, sottoscritta).
In DRY_RUN / sviluppo l'uso e' di sviluppo. Vedi `social/remotion/README.md` e
https://www.remotion.dev/docs/licensing

## Env (NON committare segreti)

Pubblicazione (impostare come secrets quando si collegano gli account):
`META_PAGE_ACCESS_TOKEN`, `META_IG_USER_ID`, `META_FB_PAGE_ID`,
`TIKTOK_ACCESS_TOKEN`, `X_BEARER_TOKEN`.
Bot Telegram: `SOCIAL_BOT_TOKEN`, `SOCIAL_ADMIN_CHAT_ID`.
`SOCIAL_LIVE=1` per uscire da DRY_RUN.
