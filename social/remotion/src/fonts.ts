import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Bundled fonts (no system-font dependency). The two DejaVu TTFs live in
// public/fonts/ so the render is reproducible on any CI machine. They are the
// same faces the site already ships in assets/fonts/.
export const FONT_FAMILY = "DejaVu Sans";

// Kick the font loads off at module scope so the work starts as soon as the
// bundle evaluates (one shared promise across every frame/worker), instead of
// per-component where concurrent renders can stall the delayRender handle.
const fontsPromise: Promise<unknown> = Promise.all([
  loadFont({
    family: FONT_FAMILY,
    url: staticFile("fonts/DejaVuSans.ttf"),
    weight: "400",
  }),
  loadFont({
    family: FONT_FAMILY,
    url: staticFile("fonts/DejaVuSans-Bold.ttf"),
    weight: "700",
  }),
]);

export const ensureFonts = (): Promise<unknown> => fontsPromise;
