// Props contract shared between the Python props builder
// (_scripts/generate_social_video.py) and the Remotion composition.
// Keep in sync: any field added here must be emitted by the Python side.

export type Lang = "en" | "it" | "es" | "de" | "fr";

export interface BrandColors {
  bgTop: string;
  bgBottom: string;
  accent: string;
  text: string;
  muted: string;
}

export interface ProductSpotlightProps {
  productName: string;
  priceFormatted: string; // already localized by Python (e.g. "12,90 €" / "$12.90")
  originalPriceFormatted: string | null;
  discountPct: number; // 0 = no badge
  imageUrl: string | null; // remote (Cloudinary) URL; null -> placeholder
  features: string[]; // short bullet lines, already localized/cleaned
  ctaText: string; // localized CTA ("Scoprilo ora" ...)
  discountBadgeLabel: string; // localized "OFF"/"SCONTO" ...
  disclosureText: string; // localized always-on line ("#adv - link affiliato")
  brandUrl: string; // "aliglobalshop.net"
  lang: Lang;
  brandColors: BrandColors;
}

export const DEFAULT_PROPS: ProductSpotlightProps = {
  productName: "AliGlobalShop Product Spotlight",
  priceFormatted: "19,90 €",
  originalPriceFormatted: "29,90 €",
  discountPct: 33,
  imageUrl: null,
  features: ["Free shipping", "Top rated", "Limited stock"],
  ctaText: "Shop now",
  discountBadgeLabel: "OFF",
  disclosureText: "#ad - affiliate link",
  brandUrl: "aliglobalshop.net",
  lang: "en",
  brandColors: {
    bgTop: "#111827",
    bgBottom: "#1e293b",
    accent: "#f97316",
    text: "#f8fafc",
    muted: "#94a3b8",
  },
};
