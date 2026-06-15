import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";
import { FONT_FAMILY } from "../fonts";

// Final CTA pill: springs in, then a soft continuous pulse (scale breathing)
// to draw the eye. Neutral wording (no "link in bio") so it is true on every
// platform; the clickable link lives in the per-platform caption.
export const Cta: React.FC<{ text: string; colors: BrandColors }> = ({ text, colors }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({ frame, fps, config: { damping: 12, mass: 0.7 } });
  const enterScale = interpolate(enter, [0, 1], [0.6, 1]);
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const pulse = 1 + 0.04 * Math.sin((frame / fps) * Math.PI * 2.2);

  return (
    <div
      style={{
        alignSelf: "flex-start",
        transform: `scale(${enterScale * pulse})`,
        transformOrigin: "left center",
        opacity,
        backgroundColor: colors.accent,
        color: colors.bgTop,
        fontFamily: FONT_FAMILY,
        fontWeight: 700,
        fontSize: 52,
        padding: "26px 56px",
        borderRadius: 60,
        boxShadow: "0 16px 40px rgba(249,115,22,0.35)",
      }}
    >
      {text}
    </div>
  );
};
