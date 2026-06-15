import React from "react";
import { Composition } from "remotion";
import { ProductSpotlight } from "./ProductSpotlight";
import { DEFAULT_PROPS } from "./types";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ProductSpotlight"
      component={ProductSpotlight as unknown as React.FC<Record<string, unknown>>}
      durationInFrames={660} // 22s @ 30fps
      fps={30}
      width={1080}
      height={1920}
      defaultProps={DEFAULT_PROPS as unknown as Record<string, unknown>}
    />
  );
};
