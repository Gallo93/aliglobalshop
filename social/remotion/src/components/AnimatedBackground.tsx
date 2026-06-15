import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";

// Brand gradient with a slow, subtle motion: the gradient angle drifts and a
// few soft blurred blobs float, so the frame is never static. Discreet, no
// flashing, no distracting particles.
export const AnimatedBackground: React.FC<{ colors: BrandColors }> = ({ colors }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();
  const t = frame / Math.max(durationInFrames - 1, 1);

  const angle = interpolate(t, [0, 1], [150, 195]);
  const blobY1 = interpolate(t, [0, 1], [0.18, 0.26]) * height;
  const blobX1 = interpolate(t, [0, 1], [0.72, 0.62]) * width;
  const blobY2 = interpolate(t, [0, 1], [0.84, 0.74]) * height;
  const blobX2 = interpolate(t, [0, 1], [0.22, 0.32]) * width;

  return (
    <AbsoluteFill
      style={{
        backgroundImage: `linear-gradient(${angle}deg, ${colors.bgTop} 0%, ${colors.bgBottom} 100%)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: blobX1,
          top: blobY1,
          width: 520,
          height: 520,
          borderRadius: "50%",
          background: colors.accent,
          opacity: 0.1,
          filter: "blur(120px)",
          transform: "translate(-50%, -50%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: blobX2,
          top: blobY2,
          width: 460,
          height: 460,
          borderRadius: "50%",
          background: colors.text,
          opacity: 0.05,
          filter: "blur(140px)",
          transform: "translate(-50%, -50%)",
        }}
      />
    </AbsoluteFill>
  );
};
