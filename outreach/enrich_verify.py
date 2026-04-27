"""Email verification.

Default verifier: Hunter's ``/v2/email-verifier`` (same API key as the
domain-search step). NeverBounce and ZeroBounce are optional secondary
checks — set their env vars and they take priority over Hunter.

Returns one of: ``valid``, ``invalid``, ``risky``, ``unknown``. Only
``valid`` is allowed past this stage; everything else is dropped to the
appropriate review log so a human can promote it later if appropriate.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .cache import JsonCache
from .config import VERIFY_CACHE, VERIFY_TTL_DAYS
from .util import log

HUNTER_BASE = "https://api.hunter.io/v2"
NEVERBOUNCE_BASE = "https://api.neverbounce.com/v4"
ZEROBOUNCE_BASE = "https://api.zerobounce.net/v2"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _http_get(url: str) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  verify retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  verify retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("verify: exhausted attempts")


def _via_hunter(email: str, api_key: str) -> str:
    """Hunter's email-verifier returns ``data.status`` ∈ {valid, invalid,
    accept_all, webmail, disposable, unknown} plus a ``score`` 0-100.

    Mapping rationale:
      - ``valid`` → valid
      - ``webmail`` → valid (real address; the editor genuinely uses gmail)
      - ``accept_all`` → risky (catch-all servers accept anything)
      - ``disposable`` → risky (mailbox exists but is throwaway)
      - ``unknown`` → unknown
      - ``invalid`` → invalid
    """
    params = {"email": email, "api_key": api_key}
    json_resp = _http_get(f"{HUNTER_BASE}/email-verifier?{urllib.parse.urlencode(params)}")
    data = json_resp.get("data") or {}
    status = (data.get("status") or "").lower()
    if status == "valid":
        return "valid"
    if status == "webmail":
        return "valid"
    if status == "invalid":
        return "invalid"
    if status in {"accept_all", "disposable"}:
        return "risky"
    return "unknown"


def _via_neverbounce(email: str, api_key: str) -> str:
    params = {"key": api_key, "email": email}
    json_resp = _http_get(f"{NEVERBOUNCE_BASE}/single/check?{urllib.parse.urlencode(params)}")
    result = json_resp.get("result")
    # NeverBounce returns: valid, invalid, disposable, catchall, unknown.
    if result == "valid":
        return "valid"
    if result == "invalid":
        return "invalid"
    if result in {"disposable", "catchall", "unknown"}:
        return "risky"
    return "unknown"


def _via_zerobounce(email: str, api_key: str) -> str:
    params = {"api_key": api_key, "email": email, "ip_address": ""}
    json_resp = _http_get(f"{ZEROBOUNCE_BASE}/validate?{urllib.parse.urlencode(params)}")
    status = (json_resp.get("status") or "").lower()
    if status == "valid":
        return "valid"
    if status == "invalid":
        return "invalid"
    if status in {"catch-all", "spamtrap", "abuse", "do_not_mail"}:
        return "risky"
    return "unknown"


def verify(
    email: str,
    *,
    hunter_key: str | None = None,
    neverbounce_key: str | None = None,
    zerobounce_key: str | None = None,
    cache: JsonCache | None = None,
) -> str:
    """Return one of: valid, invalid, risky, unknown.

    Priority: NeverBounce > ZeroBounce > Hunter. The dedicated verifiers
    are slightly more aggressive at catch-all detection, so when one is
    configured we use it; otherwise we fall back to Hunter (which uses
    the same key as the domain-search step).
    """
    if not email:
        return "invalid"
    cache = cache or JsonCache(VERIFY_CACHE, ttl_days=VERIFY_TTL_DAYS)
    cached = cache.get(email)
    if cached is not None:
        return cached

    if neverbounce_key:
        verdict = _via_neverbounce(email, neverbounce_key)
    elif zerobounce_key:
        verdict = _via_zerobounce(email, zerobounce_key)
    elif hunter_key:
        verdict = _via_hunter(email, hunter_key)
    else:
        raise RuntimeError(
            "no verifier key configured "
            "(set HUNTER_API_KEY, NEVERBOUNCE_API_KEY, or ZEROBOUNCE_API_KEY)"
        )
    cache.set(email, verdict)
    return verdict
