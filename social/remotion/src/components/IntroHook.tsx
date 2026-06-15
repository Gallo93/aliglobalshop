import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";
import { FONT_FAMILY } from "../fonts";

// Opening hook: the product name animates in big and centered, then the whole
// block scales/fades down as the main scene takes over (handled by Sequence
// timing in the composition). Words rise in with a small stagger.
export const IntroHook: React.FC<{ productName: string; colors: BrandColors }> = ({
  productName,
  colors,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const words = productName.split(" ").slice(0, 6);
  // Exit: fade/scale out over the last 12 frames of this sequence.
  const exit = interpolate(frame, [durationInFrames - 12, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitScale = interpolate(exit, [0, 1], [1.1, 1]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 90px",
        opacity: exit,
        transform: `scale(${exitScale})`,
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 18 }}>
        {words.map((w, i) => {
          const enter = spring({ frame: frame - i * 4, fps, config: { damping: 14 } });
          const y = interpolate(enter, [0, 1], [70, 0]);
          const o = interpolate(frame - i * 4, [0, 8], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <span
              key={i}
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 700,
                fontSize: 84,
                color: i % 2 === 0 ? colors.text : colors.accent,
                transform: `translateY(${y}px)`,
                opacity: o,
                lineHeight: 1.05,
                textAlign: "center",
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
