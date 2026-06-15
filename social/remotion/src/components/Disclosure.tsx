import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { FONT_FAMILY } from "../fonts";

// ALWAYS-ON affiliate disclosure, pinned top-left, high contrast. It fades in
// fast at the very start and then stays fully visible for the whole clip
// (compliance: it must never disappear). Localized text comes from props.
export const Disclosure: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        top: 56,
        left: 48,
        opacity,
        backgroundColor: "rgba(0,0,0,0.78)",
        color: "#ffffff",
        fontFamily: FONT_FAMILY,
        fontWeight: 700,
        fontSize: 38,
        padding: "16px 28px",
        borderRadius: 18,
        letterSpacing: 0.3,
      }}
    >
      {text}
    </div>
  );
};
