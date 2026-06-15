import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { BrandColors } from "../types";
import { FONT_FAMILY } from "../fonts";

// Rounded product card: scales/springs in, then a slow ken-burns zoom + drift
// runs for the rest of the clip so the image always feels alive. A discount
// badge pops in on top. Falls back to a branded placeholder when imageUrl null.
export const ProductCard: React.FC<{
  imageUrl: string | null;
  productName: string;
  discountPct: number;
  discountBadgeLabel: string;
  colors: BrandColors;
}> = ({ imageUrl, productName, discountPct, discountBadgeLabel, colors }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 14, mass: 0.7 } });
  const scaleIn = interpolate(enter, [0, 1], [0.8, 1]);
  const opacity = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });

  // Ken-burns: zoom 1.0 -> 1.12 and a gentle vertical drift across the clip.
  const t = frame / Math.max(durationInFrames - 1, 1);
  const kenZoom = interpolate(t, [0, 1], [1.0, 1.12]);
  const kenY = interpolate(t, [0, 1], [0, -28]);

  const badgePop = spring({
    frame: frame - 18,
    fps,
    config: { damping: 10, mass: 0.5 },
  });

  const CARD = 760;

  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center" }}>
      <div
        style={{
          marginTop: 230,
          width: CARD,
          height: CARD,
          borderRadius: 48,
          overflow: "hidden",
          position: "relative",
          transform: `scale(${scaleIn})`,
          opacity,
          boxShadow: "0 30px 80px rgba(0,0,0,0.45)",
          backgroundColor: "#334155",
        }}
      >
        {imageUrl ? (
          <Img
            src={imageUrl}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${kenZoom}) translateY(${kenY}px)`,
            }}
          />
        ) : (
          <AbsoluteFill
            style={{
              justifyContent: "center",
              alignItems: "center",
              backgroundColor: "#334155",
              color: colors.muted,
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 60,
              transform: `scale(${kenZoom}) translateY(${kenY}px)`,
            }}
          >
            {(productName.split(" ")[0] || "AliGlobalShop").slice(0, 14)}
          </AbsoluteFill>
        )}

        {discountPct > 0 ? (
          <div
            style={{
              position: "absolute",
              top: 28,
              left: 28,
              transform: `scale(${badgePop})`,
              backgroundColor: colors.accent,
              color: colors.bgTop,
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 50,
              padding: "12px 28px",
              borderRadius: 22,
            }}
          >
            {`-${discountPct}% ${discountBadgeLabel}`}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
