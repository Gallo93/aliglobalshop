import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";
import { FONT_FAMILY } from "../fonts";

// Feature bullets enter in sequence (stagger): each line slides in from the
// left a few frames after the previous one, with a small accent dot.
export const Features: React.FC<{ items: string[]; colors: BrandColors }> = ({
  items,
  colors,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const STAGGER = 7;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {items.slice(0, 4).map((item, i) => {
        const local = frame - i * STAGGER;
        const enter = spring({ frame: local, fps, config: { damping: 16, mass: 0.6 } });
        const x = interpolate(enter, [0, 1], [-60, 0]);
        const opacity = interpolate(local, [0, 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              transform: `translateX(${x}px)`,
              opacity,
            }}
          >
            <div
              style={{
                width: 18,
                height: 18,
                borderRadius: "50%",
                backgroundColor: colors.accent,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 400,
                fontSize: 44,
                color: colors.text,
              }}
            >
              {item}
            </span>
          </div>
        );
      })}
    </div>
  );
};
