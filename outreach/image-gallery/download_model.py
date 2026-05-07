"""One-shot helper to fetch the Real-ESRGAN x4plus ONNX weights.

The model is ~64 MB and is not committed to the repo. Run this once
locally, or call it from CI before ``enhance.py``.

    python download_model.py
    python download_model.py --url https://example.com/custom.onnx --out models/custom.onnx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from config import DEFAULT_MODEL_PATH, DEFAULT_REALESRGAN_URL, USER_AGENT, ensure_dirs


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 1024 * 1024:
        print(f"Already present: {out} ({out.stat().st_size // (1024 * 1024)} MB)")
        return
    print(f"Downloading {url} → {out}")
    with requests.get(url, headers={"User-Agent": USER_AGENT},
                      stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        seen = 0
        with out.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                seen += len(chunk)
                if total:
                    pct = seen / total * 100
                    sys.stdout.write(f"\r  {seen // (1024 * 1024)} / {total // (1024 * 1024)} MB ({pct:.0f}%)")
                    sys.stdout.flush()
        if total:
            sys.stdout.write("\n")
    print(f"Saved {out} ({out.stat().st_size // (1024 * 1024)} MB)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_REALESRGAN_URL)
    p.add_argument("--out", type=Path, default=DEFAULT_MODEL_PATH)
    args = p.parse_args()
    ensure_dirs()
    download(args.url, args.out)


if __name__ == "__main__":
    main()
