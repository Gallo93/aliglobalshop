# Reel engine (Remotion) - ProductSpotlight

Animated vertical reel (9:16, 1080x1920, 30fps, ~22s, no audio) for the
AliGlobalShop social pipeline. Pure motion graphics rendered from a props file:
intro hook, ken-burns product card, spring price + discount badge, staggered
features, pulsing CTA, drifting brand background, and an always-on affiliate
disclosure. I font DejaVu vengono copiati in `public/fonts/` da `assets/fonts/`
al build (no font di sistema, no binari duplicati nel repo): lo fa
`generate_social_video.py` in locale e uno step dedicato nel workflow CI.

## Come funziona

1. `_scripts/generate_social_video.py` (engine `remotion`, default) scrive
   `out/social/<slug>-<lang>.props.json` con i dati del prodotto e il prezzo gia
   localizzato (stesso `format_price` di build.py).
2. Remotion legge quei props e renderizza l'MP4:

```bash
cd social/remotion
npm ci
# i font vengono copiati da ../../assets/fonts in public/fonts
mkdir -p public/fonts && cp ../../assets/fonts/DejaVuSans*.ttf public/fonts/
# render usando i props generati da Python
npx remotion render ProductSpotlight ../../out/social/<slug>-<lang>.mp4 \
  --props=../../out/social/<slug>-<lang>.props.json
# anteprima interattiva nel browser
npx remotion studio
```

In locale `generate_social_video.py --lang it` copia i font e lancia anche il
render se trova Node e `node_modules/`; altrimenti scrive solo i props e il
render lo fa la CI (`.github/workflows/social_video.yml`).

## Props (contratto)

Vedi `src/types.ts` (`ProductSpotlightProps`). Ogni campo emesso da Python deve
restare allineato a questa interfaccia: `productName`, `priceFormatted`,
`originalPriceFormatted`, `discountPct`, `imageUrl`, `features[]`, `ctaText`,
`discountBadgeLabel`, `disclosureText`, `brandUrl`, `lang`, `brandColors`.

## Componenti

| File | Scena |
|------|-------|
| `src/ProductSpotlight.tsx` | composizione: orchestra intro + scena + disclosure |
| `src/components/IntroHook.tsx` | titolo animato di apertura |
| `src/components/ProductCard.tsx` | card prodotto ken-burns + badge sconto |
| `src/components/PriceBlock.tsx` | prezzo spring/pop + prezzo barrato |
| `src/components/Features.tsx` | bullet feature in stagger |
| `src/components/Cta.tsx` | pill CTA con pulse |
| `src/components/AnimatedBackground.tsx` | gradiente brand in leggero movimento |
| `src/components/Disclosure.tsx` | disclosure SEMPRE visibile (compliance) |

## NOTA LICENZA (da verificare prima del go-live commerciale)

Remotion NON e' MIT puro: ha una licenza che per le **aziende** puo' richiedere
la **Remotion Company License** a pagamento sopra una certa soglia di dipendenti
/ fatturato. Questo progetto e' un sito di affiliazione, quindi **prima di
qualunque uso commerciale (go-live, pubblicazione reale dei reel)** va verificata
la licenza Remotion per il nostro caso e, se dovuta, sottoscritta la Company
License. Finche' restiamo in DRY_RUN / sviluppo (nessuna pubblicazione) l'uso e'
di sviluppo. Riferimento: https://www.remotion.dev/docs/licensing

## Niente audio

I reel sono silenziosi: la musica richiede licenza commerciale, valutata
separatamente piu' avanti.
