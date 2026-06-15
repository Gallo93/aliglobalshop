# Video social - Fase 1 (DRY_RUN)

Pipeline per generare video verticali "Product Spotlight" dai prodotti del
catalogo, con caption compliant e approvazione via Telegram. Tutto in DRY_RUN:
nessuna pubblicazione reale, nessun token richiesto adesso.

## File

| File | Ruolo |
|------|-------|
| `social_common.py` | helper condivisi: catalogo, prezzo localizzato (come build.py), disclosure |
| `social_caption.py` | caption compliant per lingua + piattaforma |
| `generate_social_video.py` | render MP4 9:16 1080x1920 silenzioso (Pillow + ffmpeg) |
| `social_publish.py` | stub pubblicazione (DRY_RUN: logga, niente rete) |
| `social_bot.py` | approvazione Telegram (anteprima + bottoni Approva/Scarta/Rigenera) |

## Uso locale

```bash
pip install Pillow requests
python _scripts/generate_social_video.py --lang it            # miglior offerta
python _scripts/generate_social_video.py --lang en --slug <slug>
python _scripts/generate_social_video.py --lang de --no-video # solo caption
```

Output in `out/social/` (NON committato): `<slug>-<lang>.mp4` +
`<slug>-<lang>.caption.txt` (una caption per piattaforma: facebook/instagram/tiktok/x).

## Approvazione Telegram

```bash
# senza token: modalita MOCK, logga il payload che invierebbe (testabile)
python _scripts/social_bot.py --lang it
python _scripts/social_bot.py --lang it --simulate approve   # simula bottone
# con token reale: long-poll dei bottoni
SOCIAL_BOT_TOKEN=... SOCIAL_ADMIN_CHAT_ID=... python _scripts/social_bot.py --serve
```

- Approva -> chiama gli stub publish (DRY_RUN, logga "pubblicherei su X")
- Scarta -> archivia video+caption in `out/social/_discarded/`
- Rigenera -> stub Fase 1 (la rigenerazione vera arriva in Fase 2)

## Workflow GitHub Actions

`.github/workflows/social_video.yml` -> `workflow_dispatch` (input: `lang`, `slug`).
Installa ffmpeg + Pillow, genera un video reale da un prodotto del catalogo,
mostra il payload di approvazione (mock) e carica MP4 + caption come **artifact**
del run (scaricabile dalla pagina del run, in fondo, sezione "Artifacts").
Nessun segreto, nessuna pubblicazione.

## Compliance

- Disclosure SEMPRE visibile nel video (overlay #ad/#adv... + "link affiliato")
  e in apertura di ogni caption.
- CTA cliccabile per piattaforma nella CAPTION: IG/TikTok "link in bio"; FB/X
  link diretto. Il video e' uno solo multipiattaforma, quindi la CTA SOVRAIMPRESSA
  e' neutra per lingua ("Scoprilo ora" / "Shop now" ...) e vera ovunque: non
  afferma "link in bio" (sarebbe falso su FB/X).
- Niente musica (richiede licenza commerciale): video silenzioso.
- Niente em-dash nei testi visibili (regola sito).

## Env futuri (NON committare segreti)

Pubblicazione (impostare come secrets quando si collegano gli account):
`META_PAGE_ACCESS_TOKEN`, `META_IG_USER_ID`, `META_FB_PAGE_ID`,
`TIKTOK_ACCESS_TOKEN`, `X_BEARER_TOKEN`.
Bot Telegram: `SOCIAL_BOT_TOKEN`, `SOCIAL_ADMIN_CHAT_ID`.
`SOCIAL_LIVE=1` per uscire da DRY_RUN (Fase 1 non lo usa mai).
