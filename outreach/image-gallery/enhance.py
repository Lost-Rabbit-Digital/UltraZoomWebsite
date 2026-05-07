"""Stage 2: enhance candidate images.

Pipeline per image:
  1. Load with PIL.
  2. Optionally tile and run through ONNX Real-ESRGAN x4plus.
     - Tiling keeps peak RAM bounded for large inputs.
     - Tile size and overlap are configurable.
  3. Stamp the "Enhanced with UltraZoom | ultrazoom.app" watermark in the
     bottom-right corner using PIL — semi-transparent, drop-shadowed for
     readability on busy images.
  4. Compress to fit ``IMGUR_MAX_BYTES``: JPEG quality steps from 95 → 70,
     then progressive resize to 4096px on the long edge.
  5. Write to enhanced/<hash>.jpg and update the DB.

Run:
    python enhance.py --limit 5 --verbose
    python enhance.py --candidate-id 42 --verbose
    REALESRGAN_ONNX_PATH=models/custom.onnx python enhance.py

The default ONNX (realesr-general-x4v3, ~5 MB) is committed to the repo
under ``models/``. Override with ``REALESRGAN_ONNX_PATH`` to swap in a
different variant; regenerate the default via ``convert_model.py``.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import (
    DEFAULT_MODEL_PATH,
    ENHANCED_DIR,
    IMGUR_MAX_BYTES,
    WATERMARK_TEXT,
    ensure_dirs,
)
from db import connect, init_db

# Real-ESRGAN x4plus expects RGB tensors normalized to [0, 1] and outputs
# 4× larger RGB tensors in the same range.
MODEL_SCALE = 4
DEFAULT_TILE = 256
DEFAULT_TILE_OVERLAP = 16

# Lazy import: only needed when actually running inference. This keeps the
# module importable in environments that don't yet have the model installed
# (e.g. for the review UI's import side effects).
_ort = None


def _load_ort():
    global _ort
    if _ort is None:
        import onnxruntime as ort  # type: ignore
        _ort = ort
    return _ort


# ---------- inference ----------

def _load_session(model_path: Path):
    ort = _load_ort()
    providers = ort.get_available_providers()
    # Prefer CUDA / CoreML if present, else CPU. CI almost always lands on CPU.
    preferred = [p for p in ["CUDAExecutionProvider", "CoreMLExecutionProvider", "CPUExecutionProvider"]
                 if p in providers]
    return ort.InferenceSession(str(model_path), providers=preferred or providers)


def _to_tensor(im: Image.Image) -> np.ndarray:
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    # NHWC -> NCHW
    return np.transpose(arr, (2, 0, 1))[None, ...]


def _from_tensor(t: np.ndarray) -> Image.Image:
    # NCHW -> HWC
    arr = np.clip(t[0], 0.0, 1.0)
    arr = np.transpose(arr, (1, 2, 0))
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), mode="RGB")


def _upscale_tiled(session, im: Image.Image, tile: int, overlap: int) -> Image.Image:
    """Run Real-ESRGAN over the image in overlapping tiles.

    Output is composited at MODEL_SCALE × resolution. Overlap pixels are
    cross-faded to avoid visible tile seams.
    """
    if tile <= 0:
        # Single-pass (fine for tiny images, OOM-prone for big ones).
        out = session.run(None, {session.get_inputs()[0].name: _to_tensor(im)})[0]
        return _from_tensor(out)

    w, h = im.size
    scale = MODEL_SCALE
    out_im = Image.new("RGB", (w * scale, h * scale))
    blend_mask_cache: dict[tuple[int, int], Image.Image] = {}

    in_name = session.get_inputs()[0].name
    step = tile - overlap
    if step <= 0:
        step = tile
    for y in range(0, h, step):
        for x in range(0, w, step):
            x2 = min(x + tile, w)
            y2 = min(y + tile, h)
            crop = im.crop((x, y, x2, y2))
            # Pad to (tile, tile) so the model sees a fixed shape if it asks.
            pad = Image.new("RGB", (tile, tile))
            pad.paste(crop, (0, 0))
            out = session.run(None, {in_name: _to_tensor(pad)})[0]
            up = _from_tensor(out)
            up = up.crop((0, 0, (x2 - x) * scale, (y2 - y) * scale))

            ox, oy = x * scale, y * scale
            if x == 0 and y == 0:
                out_im.paste(up, (ox, oy))
                continue
            mask = blend_mask_cache.get(up.size)
            if mask is None:
                mask = _seam_mask(up.size, overlap_px=overlap * scale,
                                  blend_left=x > 0, blend_top=y > 0)
                blend_mask_cache[up.size] = mask
            out_im.paste(up, (ox, oy), mask)
    return out_im


def _seam_mask(size: tuple[int, int], *, overlap_px: int,
               blend_left: bool, blend_top: bool) -> Image.Image:
    """Linear-falloff alpha mask used to cross-fade tile borders."""
    w, h = size
    mask = Image.new("L", (w, h), 255)
    if overlap_px <= 0:
        return mask
    px = mask.load()
    for j in range(h):
        for i in range(w):
            a = 255
            if blend_left and i < overlap_px:
                a = min(a, int(255 * (i / max(overlap_px - 1, 1))))
            if blend_top and j < overlap_px:
                a = min(a, int(255 * (j / max(overlap_px - 1, 1))))
            px[i, j] = a
    return mask


# ---------- watermark + compress ----------

def _watermark(im: Image.Image, text: str) -> Image.Image:
    """Bottom-right watermark, semi-transparent, with a soft drop shadow.

    Text size scales to ~1.2% of the long edge. We never let it dominate.
    """
    base = im.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    long_edge = max(base.size)
    font_px = max(14, int(long_edge * 0.012))
    font = _load_font(font_px)

    # Pillow ≥9.2 has textbbox; older has textsize. Support both.
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    margin = max(12, font_px)
    x = base.size[0] - tw - margin
    y = base.size[1] - th - margin

    # Shadow (slightly offset, dark, blurred via small alpha radius).
    for dx, dy, alpha in [(2, 2, 160), (1, 1, 200)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, alpha))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 220))

    return Image.alpha_composite(base, overlay).convert("RGB")


def _load_font(px: int):
    # Bundled DejaVu ships with Pillow on most platforms.
    candidates = [
        "DejaVuSans-Bold.ttf",
        "Arial Bold.ttf",
        "Arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _compress_to_limit(im: Image.Image, max_bytes: int) -> bytes:
    """JPEG-encode under ``max_bytes``. Quality first, then resize."""
    img = im
    long_edge_cap = max(img.size)
    while True:
        for q in (95, 90, 85, 80, 75, 70):
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
            if buf.tell() <= max_bytes:
                return buf.getvalue()
        # Still too big — shrink long edge by 15% and retry the quality ladder.
        long_edge_cap = int(long_edge_cap * 0.85)
        if long_edge_cap < 1024:
            # Anything smaller than this is no longer worth shipping. Give up
            # and return whatever we managed at q=70 + cap=1024.
            buf = BytesIO()
            scale = 1024 / max(img.size)
            img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)),
                             Image.LANCZOS)
            img.save(buf, format="JPEG", quality=70, optimize=True, progressive=True)
            return buf.getvalue()
        scale = long_edge_cap / max(img.size)
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)),
                         Image.LANCZOS)


# ---------- DB plumbing ----------

def _candidates_to_enhance(conn, *, limit: Optional[int],
                           candidate_id: Optional[int]) -> list:
    if candidate_id is not None:
        sql = "SELECT * FROM candidates WHERE id = ?"
        return list(conn.execute(sql, (candidate_id,)))
    sql = (
        "SELECT * FROM candidates "
        "WHERE status = 'new' AND enhanced_path IS NULL "
        "ORDER BY id DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    return list(conn.execute(sql))


def _mark_enhanced(conn, cid: int, *, enhanced_path: Path,
                   width: int, height: int, n_bytes: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rel = str(enhanced_path.relative_to(ENHANCED_DIR.parent))
    conn.execute(
        "UPDATE candidates SET enhanced_path=?, enhanced_width=?, enhanced_height=?, "
        "enhanced_bytes=?, enhanced_at=?, enhance_error=NULL, status='enhanced' "
        "WHERE id=?",
        (rel, width, height, n_bytes, now, cid),
    )


def _mark_failed(conn, cid: int, err: str) -> None:
    conn.execute(
        "UPDATE candidates SET enhance_error=? WHERE id=?",
        (err[:500], cid),
    )


# ---------- entry point ----------

def enhance_one(session, row, *, tile: int, overlap: int, verbose: bool) -> dict:
    src_path = Path(row["image_path"])
    if not src_path.is_absolute():
        src_path = Path(__file__).parent.parent / src_path
    im = Image.open(src_path).convert("RGB")
    t0 = time.time()
    upscaled = _upscale_tiled(session, im, tile=tile, overlap=overlap)
    t1 = time.time()
    stamped = _watermark(upscaled, WATERMARK_TEXT)
    data = _compress_to_limit(stamped, IMGUR_MAX_BYTES)

    out_path = ENHANCED_DIR / row["image_hash"][:2] / f"{row['image_hash']}.jpg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    if verbose:
        print(f"[enhance] cand={row['id']} {im.size} → {stamped.size}  "
              f"upscale={t1 - t0:.1f}s  out={len(data) // 1024}KB")
    return {
        "path": out_path,
        "width": stamped.size[0],
        "height": stamped.size[1],
        "bytes": len(data),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 2: enhance candidates with Real-ESRGAN.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process at most N candidates (default: all status='new')")
    p.add_argument("--candidate-id", type=int, default=None,
                   help="Re-enhance a single candidate by id (overrides --limit)")
    p.add_argument("--tile", type=int, default=DEFAULT_TILE,
                   help="Tile size in pixels; 0 disables tiling")
    p.add_argument("--overlap", type=int, default=DEFAULT_TILE_OVERLAP)
    p.add_argument("--model", type=Path, default=None,
                   help=f"Path to ONNX model (default: $REALESRGAN_ONNX_PATH or {DEFAULT_MODEL_PATH})")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    ensure_dirs()
    init_db()

    model_path = args.model or Path(os.environ.get("REALESRGAN_ONNX_PATH") or DEFAULT_MODEL_PATH)
    if not model_path.exists():
        print(
            f"ONNX model not found at {model_path}. "
            f"Run `python convert_model.py` or set REALESRGAN_ONNX_PATH.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.verbose:
        print(f"[enhance] loading model: {model_path}")
    session = _load_session(model_path)

    enhanced = 0
    failed = 0
    with connect() as conn:
        rows = _candidates_to_enhance(
            conn, limit=args.limit, candidate_id=args.candidate_id,
        )
        for row in rows:
            try:
                res = enhance_one(session, row, tile=args.tile,
                                  overlap=args.overlap, verbose=args.verbose)
                _mark_enhanced(
                    conn, row["id"],
                    enhanced_path=res["path"],
                    width=res["width"], height=res["height"], n_bytes=res["bytes"],
                )
                enhanced += 1
            except Exception as e:
                failed += 1
                _mark_failed(conn, row["id"], str(e))
                print(f"[enhance] cand={row['id']} FAILED: {e}", file=sys.stderr)

    print(f"Enhanced {enhanced} / failed {failed}")


if __name__ == "__main__":
    main()
