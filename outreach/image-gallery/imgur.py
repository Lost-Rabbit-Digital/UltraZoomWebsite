"""Thin wrapper around the Imgur v3 API.

Two auth modes:
  * Anonymous (Client-ID header): supports /3/upload, but submission to the
    public gallery requires a real user, so this is mostly for local
    smoke-testing.
  * OAuth (Bearer access_token): /3/gallery/<id> with a refresh-token-derived
    access token. CI uses this.

Required env vars in CI:
  IMGUR_CLIENT_ID      Imgur app client id
  IMGUR_CLIENT_SECRET  paired secret (only used to refresh access tokens)
  IMGUR_REFRESH_TOKEN  long-lived refresh token from a one-time OAuth dance

Local-only env vars:
  IMGUR_ACCESS_TOKEN   short-lived; if present we skip the refresh step
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from config import USER_AGENT

API_BASE = "https://api.imgur.com/3"
TOKEN_URL = "https://api.imgur.com/oauth2/token"


class ImgurError(RuntimeError):
    pass


@dataclass
class UploadResult:
    image_id: str
    deletehash: Optional[str]
    link: Optional[str]


@dataclass
class GalleryResult:
    gallery_url: str


# ---------- auth ----------

def _refresh_access_token() -> str:
    cid = os.environ.get("IMGUR_CLIENT_ID")
    secret = os.environ.get("IMGUR_CLIENT_SECRET")
    refresh = os.environ.get("IMGUR_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        raise ImgurError(
            "Need IMGUR_CLIENT_ID, IMGUR_CLIENT_SECRET, IMGUR_REFRESH_TOKEN "
            "to mint an access token."
        )
    r = requests.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh,
            "client_id": cid,
            "client_secret": secret,
            "grant_type": "refresh_token",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if not r.ok:
        raise ImgurError(f"OAuth refresh failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _bearer_headers() -> dict:
    token = os.environ.get("IMGUR_ACCESS_TOKEN") or _refresh_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
    }


def _client_id_headers() -> dict:
    cid = os.environ.get("IMGUR_CLIENT_ID")
    if not cid:
        raise ImgurError("IMGUR_CLIENT_ID is required")
    return {
        "Authorization": f"Client-ID {cid}",
        "User-Agent": USER_AGENT,
    }


# ---------- ops ----------

def upload_image(path: Path, *, title: str | None = None,
                 description: str | None = None,
                 anonymous: bool = False) -> UploadResult:
    """Upload one image. With OAuth, the image is owned by the user account."""
    headers = _client_id_headers() if anonymous else _bearer_headers()
    with path.open("rb") as f:
        data = {}
        if title:       data["title"] = title[:128]
        if description: data["description"] = description[:1024]
        r = requests.post(
            f"{API_BASE}/upload",
            headers=headers,
            data=data,
            files={"image": (path.name, f, "image/jpeg")},
            timeout=120,
        )
    if not r.ok:
        raise ImgurError(f"upload failed: {r.status_code} {r.text}")
    payload = r.json().get("data") or {}
    return UploadResult(
        image_id=payload.get("id"),
        deletehash=payload.get("deletehash"),
        link=payload.get("link"),
    )


def submit_to_gallery(image_id: str, *, title: str, tags: list[str],
                      mature: bool = False) -> GalleryResult:
    """Promote an uploaded image into the public Imgur gallery.

    Tags are space-or-comma separated on the wire; we normalize to a comma
    list.  ``title`` is mandatory and must be ≥5 chars per Imgur's rules.
    """
    if len(title) < 5:
        raise ImgurError(f"title too short for gallery submission: {title!r}")
    payload = {
        "title": title[:128],
        "mature": "true" if mature else "false",
    }
    if tags:
        payload["tags"] = ",".join(t.strip() for t in tags if t.strip())[:1000]
    r = requests.post(
        f"{API_BASE}/gallery/{image_id}",
        headers=_bearer_headers(),
        data=payload,
        timeout=60,
    )
    if not r.ok:
        raise ImgurError(f"gallery submit failed: {r.status_code} {r.text}")
    return GalleryResult(gallery_url=f"https://imgur.com/gallery/{image_id}")


def fetch_gallery_stats(image_id: str) -> dict:
    """Return the current view/upvote counts for a posted gallery item."""
    r = requests.get(
        f"{API_BASE}/gallery/album/{image_id}",
        headers=_bearer_headers(),
        timeout=30,
    )
    if r.status_code == 404:
        # Not a gallery album — try gallery/image (Imgur classifies single
        # images and albums under different endpoints).
        r = requests.get(
            f"{API_BASE}/gallery/image/{image_id}",
            headers=_bearer_headers(),
            timeout=30,
        )
    if not r.ok:
        raise ImgurError(f"stats fetch failed: {r.status_code} {r.text}")
    return r.json().get("data") or {}
