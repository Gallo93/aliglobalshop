import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import type { ProductSpotlightProps } from "./types";
import { ensureFonts, FONT_STACK } from "./fonts";
import { AnimatedBackground } from "./components/AnimatedBackground";
import { Disclosure } from "./components/Disclosure";
import { IntroHook } from "./components/IntroHook";
import { ProductCard } from "./components/ProductCard";
import { PriceBlock } from "./components/PriceBlock";
import { Features } from "./components/Features";
import { Cta } from "./components/Cta";

const INTRO_FRAMES = 70; // ~2.3s hook

export const ProductSpotlight: React.FC<ProductSpotlightProps> = (props) => {
  const { durationInFrames } = useVideoConfig();

  // Kick off (idempotent) font loading. The delayRender handle lives inside
  // ensureFonts() and is ALWAYS released, so the render never times out on
  // fonts; here we only need to start it.
  React.useEffect(() => {
    void ensureFonts();
  }, []);

  const {
    productName,
    priceFormatted,
    originalPriceFormatted,
    discountPct,
    imageUrl,
    features,
    ctaText,
    discountBadgeLabel,
    disclosureText,
    brandUrl,
    colors,
  } = {
    ...props,
    colors: props.brandColors,
  };

  const mainDuration = durationInFrames - INTRO_FRAMES;

  return (
    <AbsoluteFill style={{ fontFamily: FONT_STACK }}>
      {/* Background drifts for the whole clip. */}
      <AnimatedBackground colors={props.brandColors} />

      {/* Intro hook. */}
      <Sequence durationInFrames={INTRO_FRAMES}>
        <IntroHook productName={productName} colors={props.brandColors} />
      </Sequence>

      {/* Main spotlight scene. */}
      <Sequence from={INTRO_FRAMES} durationInFrames={mainDuration}>
        <AbsoluteFill>
          <ProductCard
            imageUrl={imageUrl}
            productName={productName}
            discountPct={discountPct}
            discountBadgeLabel={discountBadgeLabel}
            colors={props.brandColors}
          />

          {/* Lower content stack. Each section is pinned at an explicit Y so
              the wrapped Sequences (absolute by default) never overlap. */}
          <Sequence>
            <div
              style={{
                position: "absolute",
                left: 70,
                right: 70,
                top: 1060,
                fontFamily: FONT_STACK,
                fontWeight: 700,
                fontSize: 54,
                color: colors.text,
                lineHeight: 1.1,
                // Clamp to 2 lines so long catalog titles never push the price
                // and features off their pinned positions.
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
                maxHeight: 130,
              }}
            >
              {productName}
            </div>
          </Sequence>

          <Sequence from={10}>
            <div style={{ position: "absolute", left: 70, top: 1210 }}>
              <PriceBlock
                priceFormatted={priceFormatted}
                originalPriceFormatted={originalPriceFormatted}
                colors={props.brandColors}
              />
            </div>
          </Sequence>

          <Sequence from={28}>
            <div style={{ position: "absolute", left: 70, right: 70, top: 1350 }}>
              <Features items={features} colors={props.brandColors} />
            </div>
          </Sequence>

          <Sequence from={70}>
            <div style={{ position: "absolute", left: 70, top: 1680 }}>
              <Cta text={ctaText} colors={props.brandColors} />
            </div>
          </Sequence>

          {/* Brand footer. */}
          <div
            style={{
              position: "absolute",
              left: 70,
              top: 1860,
              fontFamily: FONT_STACK,
              fontWeight: 400,
              fontSize: 34,
              color: colors.muted,
            }}
          >
            {brandUrl}
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* Disclosure is OUTSIDE the sequences => visible for the entire clip. */}
      <Disclosure text={disclosureText} />
    </AbsoluteFill>
  );
};
