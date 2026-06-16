import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { BrandColors } from "../types";

// Optional cinematic b-roll background for the intro hook. The clip name is a
// staticFile-relative path ("intro/<file>.mp4") produced by the Python side
// from the Pexels API. It covers the full 1080x1920 frame (object-fit: cover),
// with a brand gradient overlay so the hook text stays legible. It fades out at
// the end of the intro sequence to hand over to the main scene.
//
// IMPORTANT (compliance): this sits BEHIND the hook text and, since the
// composition renders the Disclosure last/outside the sequences, also behind
// the always-on affiliate disclosure. It never covers the disclosure.
export const IntroVideo: React.FC<{ src: string; colors: BrandColors }> = ({
  src,
  colors,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return (
    <AbsoluteFill style={{ opacity: fadeOut }}>
      <OffthreadVideo
        src={staticFile(src)}
        muted
        // Loop so a short clip still covers the whole intro window.
        loop
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      {/* Brand gradient overlay to keep the hook text readable. */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(180deg, ${colors.bgTop}cc 0%, ${colors.bgBottom}99 55%, ${colors.bgTop}dd 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};
