"""Stage 1 source adapters.

Each module exposes ``discover() -> list[Candidate]`` where a Candidate is
the dataclass defined in ``sources.base``. Callers pick which adapters to
run; ``discover.py`` orchestrates them.
"""
