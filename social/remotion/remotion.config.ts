import { Config } from "@remotion/cli/config";

// Vertical reel encoding defaults. H.264 + yuv420p so the MP4 plays on every
// social platform; no audio track (music needs a commercial licence).
Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
Config.setPixelFormat("yuv420p");
Config.setOverwriteOutput(true);
// Headless Chromium flags that keep CI (GitHub Actions ubuntu) happy.
Config.setChromiumOpenGlRenderer("angle");
// Give font/image loading room under concurrent rendering.
Config.setDelayRenderTimeoutInMilliseconds(60000);
