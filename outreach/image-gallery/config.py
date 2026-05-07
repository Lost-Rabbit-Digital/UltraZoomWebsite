"""Shared configuration and paths for the image-gallery pipeline."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).parent

# On-disk layout. Each stage owns one folder.
CANDIDATES_DIR = ROOT / "candidates"   # Stage 1: raw downloads + .json sidecars
ENHANCED_DIR   = ROOT / "enhanced"     # Stage 2: upscaled + watermarked + sidecar
POSTED_DIR     = ROOT / "posted"       # Stage 4: archived copies of what shipped
MODELS_DIR     = ROOT / "models"       # Stage 2: ONNX weights cache

DB_PATH = ROOT / "gallery.db"

# Imgur enforces 20 MB per image for the standard API. Stage 2 resizes and
# re-encodes JPEG quality until it fits.
IMGUR_MAX_BYTES = 20 * 1024 * 1024

# Default upscaler. The realesr-general-x4v3 ONNX is committed to the repo
# (~5 MB) and regenerated from xinntao's .pth via convert_model.py if the
# weights ever change. Override via REALESRGAN_ONNX_PATH to use a different
# variant locally.
DEFAULT_MODEL_PATH = MODELS_DIR / "realesr-general-x4v3.onnx"

# Posting window: 10am ET to midnight ET, every 2 hours = 8 slots/day.
# Stored as UTC hours in the queue. ET is UTC-5 (EST) or UTC-4 (EDT); the
# scheduler picks whichever is currently in effect when slots are assigned.
POST_WINDOW_LOCAL_START_HOUR = 10   # 10am local
POST_WINDOW_LOCAL_END_HOUR   = 24   # midnight (exclusive)
POST_WINDOW_TZ               = "America/New_York"
POST_INTERVAL_HOURS          = 2

WATERMARK_TEXT = "Enhanced with UltraZoom | ultrazoom.app"

# Reddit polling defaults. Override per-run via discover.py CLI flags.
DEFAULT_SUBREDDITS = [
    "spaceporn",
    "earthporn",
    "astrophotography",
    "natureismetal",
    "interestingasfuck",
    "pics",
]
REDDIT_MIN_SCORE = 500
REDDIT_TOP_WINDOW = "day"     # one of: hour, day, week, month, year, all

# Wikimedia Commons / NASA. No keys required; NASA's APOD takes DEMO_KEY but
# we recommend a real key for non-trivial volume.
NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = (
    "UltraZoomGalleryBot/1.0 (https://ultrazoom.app; bot@lostrabbitdigital.com)"
)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def ensure_dirs() -> None:
    for d in (CANDIDATES_DIR, ENHANCED_DIR, POSTED_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
