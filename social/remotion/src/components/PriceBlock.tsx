import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";
import { FONT_FAMILY } from "../fonts";

// Price enters with a spring "pop" (scale + slide up). The original price sits
// next to it with a strike-through. Both already localized by Python.
export const PriceBlock: React.FC<{
  priceFormatted: string;
  originalPriceFormatted: string | null;
  colors: BrandColors;
}> = ({ priceFormatted, originalPriceFormatted, colors }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pop = spring({ frame, fps, config: { damping: 9, mass: 0.6, stiffness: 120 } });
  const scale = interpolate(pop, [0, 1], [0.4, 1]);
  const y = interpolate(pop, [0, 1], [40, 0]);
  const opacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 24,
        transform: `translateY(${y}px) scale(${scale})`,
        transformOrigin: "left bottom",
        opacity,
      }}
    >
      <span
        style={{
          fontFamily: FONT_FAMILY,
          fontWeight: 700,
          fontSize: 104,
          color: colors.accent,
          lineHeight: 1,
        }}
      >
        {priceFormatted}
      </span>
      {originalPriceFormatted ? (
        <span
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 48,
            color: colors.muted,
            textDecoration: "line-through",
            paddingBottom: 12,
          }}
        >
          {originalPriceFormatted}
        </span>
      ) : null}
    </div>
  );
};
