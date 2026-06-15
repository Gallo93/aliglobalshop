import { loadFont } from "@remotion/fonts";
import { staticFile, delayRender, continueRender } from "remotion";

// Bundled fonts (no system-font dependency in the happy path). The two DejaVu
// TTFs are copied into public/fonts/ from assets/fonts/ by the CI workflow (and
// by generate_social_video.py locally), so staticFile() resolves them from the
// Remotion bundle. They are the same faces the site ships in assets/fonts/.
//
// IMPORTANT (CI): we own the delayRender handle here instead of letting
// loadFont register its own. In headless Chromium a stalled font fetch left
// loadFont's internal handle dangling -> delayRender timeout -> render exit 1.
// Here the handle is ALWAYS released (finally), with a short timeout, so the
// render can never hang on fonts. If the load fails we fall back to a system
// sans-serif via FONT_STACK and continue.
export const FONT_FAMILY = "DejaVu Sans";
// Use this as the actual CSS fontFamily so text renders even if the webfont is
// not ready (system fallback), never an empty/invisible glyph box.
export const FONT_STACK = `"${FONT_FAMILY}", sans-serif`;

const loadOne = (file: string, weight: "400" | "700"): Promise<unknown> =>
  loadFont({
    family: FONT_FAMILY,
    url: staticFile(file),
    weight,
    // Do not let a single missing/slow font abort the whole render.
  }).catch((err) => {
    // eslint-disable-next-line no-console
    console.warn(`[fonts] loadFont failed for ${file}, using system fallback`, err);
    return undefined;
  });

// Kick the loads off once at module scope (one shared promise across every
// frame/worker). We attach our own delayRender so the renderer waits for the
// fonts, but with a hard ceiling and a guaranteed release.
let fontsPromise: Promise<unknown> | null = null;

export const ensureFonts = (): Promise<unknown> => {
  if (fontsPromise) {
    return fontsPromise;
  }
  // Short, self-clearing handle: the global config gives 60s, we cap fonts well
  // under that so a font stall degrades to the system font instead of failing.
  const handle = delayRender("loading fonts", { timeoutInMilliseconds: 20000 });
  fontsPromise = Promise.all([
    loadOne("fonts/DejaVuSans.ttf", "400"),
    loadOne("fonts/DejaVuSans-Bold.ttf", "700"),
  ])
    .catch(() => undefined)
    .finally(() => {
      // ALWAYS release, success or failure, so the render never times out here.
      continueRender(handle);
    });
  return fontsPromise;
};
