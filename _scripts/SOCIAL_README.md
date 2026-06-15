# Video social - reel animati (DRY_RUN)

Pipeline per generare reel verticali "Product Spotlight" dai prodotti del
catalogo: ora **reel animati veri** (motion graphics via Remotion), con caption
compliant e approvazione via Telegram. Tutto in DRY_RUN: nessuna pubblicazione
reale, nessun token richiesto adesso.

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
| `social_publish.py` | stub pubblicazione (DRY_RUN: logga, niente rete) |
| `social_bot.py` | approvazione Telegram (anteprima + bottoni Approva/Scarta/Rigenera) |

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
facebook/instagram/tiktok/x).

## Approvazione Telegram

```bash
python _scripts/social_bot.py --lang it
python _scripts/social_bot.py --lang it --simulate approve   # simula bottone
SOCIAL_BOT_TOKEN=... SOCIAL_ADMIN_CHAT_ID=... python _scripts/social_bot.py --serve
```

- Approva -> chiama gli stub publish (DRY_RUN, logga "pubblicherei su X")
- Scarta -> archivia video+caption in `out/social/_discarded/`
- Rigenera -> stub (la rigenerazione vera arriva piu' avanti)

## Workflow GitHub Actions

`.github/workflows/social_video.yml` -> `workflow_dispatch` (input: `lang`, `slug`).
Setup Python + Node 20, `npm ci` in `social/remotion`, step Python che costruisce
i props, `npx remotion render` -> MP4, payload di approvazione mock, e carica
MP4 + caption + props come **artifact** del run. Nessun segreto, nessuna
pubblicazione.

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

## Env futuri (NON committare segreti)

Pubblicazione (impostare come secrets quando si collegano gli account):
`META_PAGE_ACCESS_TOKEN`, `META_IG_USER_ID`, `META_FB_PAGE_ID`,
`TIKTOK_ACCESS_TOKEN`, `X_BEARER_TOKEN`.
Bot Telegram: `SOCIAL_BOT_TOKEN`, `SOCIAL_ADMIN_CHAT_ID`.
`SOCIAL_LIVE=1` per uscire da DRY_RUN (non usato adesso).
