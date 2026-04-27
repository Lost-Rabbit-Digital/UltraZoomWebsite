"""Discovery orchestrator.

Picks a seed bucket via rotation, fans out to Brave + Exa + RSS, and
returns merged candidate dicts. Each source tags its outputs with
``source`` and ``seed_used`` so qualification can score by provenance.
"""

from __future__ import annotations

from typing import Any

from . import discover_brave, discover_exa, discover_rss
from .config import Config
from .seeds import SeedSelection
from .util import log, now_iso


def _tag(items: list[dict[str, Any]], *, source: str, seed: str) -> list[dict[str, Any]]:
    discovered_at = now_iso()
    tagged: list[dict[str, Any]] = []
    for item in items:
        if not item.get("url"):
            continue
        out = dict(item)
        out["source"] = source
        out["seed_used"] = seed
        out["discovered_at"] = discovered_at
        tagged.append(out)
    return tagged


def run(
    cfg: Config,
    selection: SeedSelection,
    *,
    per_query: int = 15,
    use_rss: bool = True,
    exa_similar_targets: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run all enabled discovery sources and return a merged list, deduped
    by URL within this run. Seen-URL/seen-domain dedupe is handled later
    in qualification so we still record every URL we pulled today.
    """
    candidates: list[dict[str, Any]] = []

    if cfg.brave_key:
        log(f"\n== brave search (bucket {selection.bucket}, {len(selection.seeds)} seeds) ==")
        for seed in selection.seeds:
            try:
                items = discover_brave.search(
                    api_key=cfg.brave_key, seed=seed, num_results=per_query
                )
            except Exception as e:  # noqa: BLE001
                log(f"  brave error on {seed!r}: {e}")
                continue
            log(f"  + [{len(items)}]  {seed[:70]}")
            candidates.extend(_tag(items, source="brave", seed=seed))
    else:
        log("brave: no BRAVE_SEARCH_API_KEY, skipping")

    if cfg.exa_key:
        # Exa pay-as-you-go pricing: $7/1k for 1-10 results, +$1 per result
        # beyond 10 — cap here to stay in the cheapest tier.
        exa_results = min(per_query, 10)
        log(f"\n== exa search (bucket {selection.bucket}, {len(selection.seeds)} seeds) ==")
        for seed in selection.seeds:
            try:
                items = discover_exa.search(
                    api_key=cfg.exa_key, query=seed, num_results=exa_results
                )
            except Exception as e:  # noqa: BLE001
                log(f"  exa error on {seed!r}: {e}")
                continue
            log(f"  + [{len(items)}]  {seed[:70]}")
            candidates.extend(_tag(items, source="exa", seed=seed))

        targets = exa_similar_targets or discover_exa.KNOWN_GOOD_TARGETS
        if targets:
            log(f"\n== exa findSimilar ({len(targets)} known-good targets) ==")
            for url in targets:
                try:
                    items = discover_exa.find_similar(
                        api_key=cfg.exa_key, url=url, num_results=exa_results
                    )
                except Exception as e:  # noqa: BLE001
                    log(f"  exa similar error on {url}: {e}")
                    continue
                log(f"  + [{len(items)}]  {url[:70]}")
                candidates.extend(_tag(items, source="exa-similar", seed=url))
    else:
        log("exa: no EXA_API_KEY, skipping")

    if use_rss:
        log("\n== rss feeds ==")
        try:
            rss_items = discover_rss.discover(feed_list_path=cfg.rss_feed_list_path)
        except Exception as e:  # noqa: BLE001
            log(f"  rss error: {e}")
            rss_items = []
        log(f"  + [{len(rss_items)}]  rss feed entries matching keyword filter")
        candidates.extend(_tag(rss_items, source="rss", seed="rss-feed"))

    # Within-run dedupe by URL. We keep the first occurrence so the
    # source priority is implicit: brave first (highest volume), then exa,
    # then rss.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in candidates:
        url = c.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(c)
    log(f"\ndiscovery: {len(unique)} unique candidates from {len(candidates)} raw")
    return unique
