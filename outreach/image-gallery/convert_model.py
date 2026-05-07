"""One-shot script: convert realesr-general-x4v3.pth (PyTorch) to ONNX.

Run once to produce ``models/realesr-general-x4v3.onnx``. The resulting
ONNX file is committed to the repo, so this script is normally only
re-run if the upstream weights change or the export tooling needs to
move to a newer opset.

    pip install torch onnx onnxruntime numpy
    python convert_model.py
    python convert_model.py --pth /path/to/weights.pth --out models/custom.onnx

The architecture is SRVGGNetCompact (xinntao's "general v3" variant) with
num_conv=32 and PReLU activations. We inline it here so the conversion
doesn't drag in basicsr.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import requests
import torch
from torch import nn

DEFAULT_PTH_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/"
    "v0.2.5.0/realesr-general-x4v3.pth"
)
DEFAULT_PTH_PATH = Path(__file__).parent / "models" / "realesr-general-x4v3.pth"
DEFAULT_ONNX_PATH = Path(__file__).parent / "models" / "realesr-general-x4v3.onnx"
SCALE = 4


class SRVGGNetCompact(nn.Module):
    """Compact VGG-style super-resolution net.

    Mirrors xinntao's SRVGGNetCompact so we can load the upstream .pth
    state dict directly. The forward pass adds a nearest-neighbour
    upsample of the input as a residual, matching upstream behaviour.
    """

    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64,
                 num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        body: list[nn.Module] = []
        body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
        body.append(nn.PReLU(num_parameters=num_feat))
        for _ in range(num_conv):
            body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            body.append(nn.PReLU(num_parameters=num_feat))
        body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        base = nn.functional.interpolate(x, scale_factor=self.upscale, mode="nearest")
        return out + base


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1024 * 1024:
        print(f"Already present: {dest} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    print(f"Saved {dest} ({dest.stat().st_size // (1024 * 1024)} MB)")


def _load_state_dict(pth_path: Path) -> dict:
    blob = torch.load(pth_path, map_location="cpu", weights_only=True)
    # Upstream releases wrap the weights under 'params' or 'params_ema'.
    if isinstance(blob, dict):
        for key in ("params_ema", "params"):
            if key in blob:
                return blob[key]
        return blob
    raise ValueError(f"Unexpected checkpoint structure in {pth_path}")


def convert(pth_path: Path, onnx_path: Path) -> None:
    state = _load_state_dict(pth_path)
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64,
                            num_conv=32, upscale=SCALE)
    model.load_state_dict(state, strict=True)
    model.eval()

    dummy = torch.randn(1, 3, 64, 64, dtype=torch.float32)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Exporting ONNX -> {onnx_path}")
    torch.onnx.export(
        model,
        (dummy,),
        str(onnx_path),
        input_names=["input"],
        output_names=["output"],
        opset_version=17,
        dynamic_axes={
            "input": {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "height", 3: "width"},
        },
        do_constant_folding=True,
        dynamo=False,
    )
    print(f"Saved {onnx_path} ({onnx_path.stat().st_size // 1024} KB)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_PTH_URL)
    p.add_argument("--pth", type=Path, default=DEFAULT_PTH_PATH)
    p.add_argument("--out", type=Path, default=DEFAULT_ONNX_PATH)
    args = p.parse_args()
    _download(args.url, args.pth)
    convert(args.pth, args.out)


if __name__ == "__main__":
    main()
