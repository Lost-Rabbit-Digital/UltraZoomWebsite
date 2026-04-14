/**
 * Record a slow, smooth scroll through the Ultra Zoom index page.
 *
 * Usage:
 *   node record-scroll.mjs [options]
 *
 * Environment variables (also settable via CLI flags):
 *   SITE_DIR   — path to the built site directory   (default: _site)
 *   OUT_DIR    — directory to write the video into   (default: recordings)
 *   WIDTH      — viewport width in pixels            (default: 1920)
 *   HEIGHT     — viewport height in pixels           (default: 1080)
 *   SCROLL_PPS — scroll speed in pixels per second   (default: 180)
 *   PAUSE_MS   — pause at the top and bottom in ms   (default: 2000)
 *   PORT       — local server port                   (default: 8787)
 */

import { chromium } from "playwright";
import { createServer } from "http";
import { readFile, mkdir } from "fs/promises";
import { join, extname, resolve } from "path";

// ── Configuration ────────────────────────────────────────
const SITE_DIR   = process.env.SITE_DIR   || "_site";
const OUT_DIR    = process.env.OUT_DIR    || "recordings";
const WIDTH      = Number(process.env.WIDTH)      || 1920;
const HEIGHT     = Number(process.env.HEIGHT)     || 1080;
const SCROLL_PPS = Number(process.env.SCROLL_PPS) || 180;
const PAUSE_MS   = Number(process.env.PAUSE_MS)   || 2000;
const PORT       = Number(process.env.PORT)       || 8787;

const MIME = {
  ".html": "text/html",
  ".css":  "text/css",
  ".js":   "application/javascript",
  ".json": "application/json",
  ".png":  "image/png",
  ".jpg":  "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif":  "image/gif",
  ".svg":  "image/svg+xml",
  ".webp": "image/webp",
  ".ico":  "image/x-icon",
};

// ── Tiny static file server ──────────────────────────────
function serveStatic(root) {
  return createServer(async (req, res) => {
    let pathname = req.url.split("?")[0];
    if (pathname.endsWith("/")) pathname += "index.html";

    const filePath = join(root, pathname);
    try {
      const data = await readFile(filePath);
      const ext  = extname(filePath).toLowerCase();
      res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });
}

// ── Main ─────────────────────────────────────────────────
async function main() {
  const siteRoot = resolve(SITE_DIR);
  const outDir   = resolve(OUT_DIR);
  await mkdir(outDir, { recursive: true });

  // Start local server
  const server = serveStatic(siteRoot);
  await new Promise((res) => server.listen(PORT, "127.0.0.1", res));
  const baseURL = `http://127.0.0.1:${PORT}`;
  console.log(`Serving ${siteRoot} at ${baseURL}`);

  // Launch browser with video recording
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    recordVideo: {
      dir: outDir,
      size: { width: WIDTH, height: HEIGHT },
    },
    // Disable smooth-scroll CSS so we control the animation ourselves
    reducedMotion: "no-preference",
  });

  const page = await context.newPage();

  // Override CSS smooth scrolling so we have full frame-by-frame control
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      const style = document.createElement("style");
      style.textContent = "html { scroll-behavior: auto !important; }";
      document.head.appendChild(style);
    });
  });

  console.log("Loading page...");
  await page.goto(baseURL, { waitUntil: "networkidle" });

  // Ensure we're at the very top
  await page.evaluate(() => window.scrollTo(0, 0));

  // Pause at the top so the viewer can take in the header
  console.log(`Pausing ${PAUSE_MS}ms at the top...`);
  await page.waitForTimeout(PAUSE_MS);

  // Smooth scroll to the bottom using small increments
  const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
  const clientHeight = await page.evaluate(() => document.documentElement.clientHeight);
  const totalScroll  = scrollHeight - clientHeight;

  console.log(`Scrolling ${totalScroll}px at ${SCROLL_PPS}px/s...`);

  // Use 60fps increments for the smoothest possible recording
  const FPS = 60;
  const pxPerTick = SCROLL_PPS / FPS;
  const tickMs    = 1000 / FPS;

  let scrolled = 0;
  while (scrolled < totalScroll) {
    const step = Math.min(pxPerTick, totalScroll - scrolled);
    await page.evaluate((s) => window.scrollBy(0, s), step);
    scrolled += step;
    // Small sleep to keep video frames flowing at real-time rate
    await page.waitForTimeout(tickMs);
  }

  // Make sure we're at the very bottom
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));

  // Pause at the bottom
  console.log(`Pausing ${PAUSE_MS}ms at the bottom...`);
  await page.waitForTimeout(PAUSE_MS);

  // Close and save
  const video = page.video();
  await page.close();

  const videoPath = await video.path();
  console.log(`Raw recording saved: ${videoPath}`);

  await context.close();
  await browser.close();
  server.close();

  console.log("Done.");
  return videoPath;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
