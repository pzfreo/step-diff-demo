"""
ISO metric thread tables and lookup helpers.

Single source of truth for the thread-related constants used across the
model — thread major diameter, tap-drill diameter, coarse pitch.

`bd_warehouse.thread` holds the authoritative ISO table; this module is
a small local shortcut that lets `gramil.parameters` validate wall
thicknesses without pulling in build123d, and gives the parts a stable
API for looking up thread geometry.

Add new thread sizes by extending `_TABLE`. Every entry MUST have
matching values across all three columns (radius, tap-drill diameter,
pitch).
"""

from __future__ import annotations

# Public type alias — the strings accepted by every lookup in this module.
# Add an entry here as well when extending `_TABLE`.
ThreadSpec = str

# Single underlying table: (major-radius mm, tap-drill diameter mm, coarse-pitch mm).
# tap-drill values are conservative (close-fit). Coarse pitch only — fine
# pitches are out of scope for this project.
_TABLE: dict[str, tuple[float, float, float]] = {
    "M2":   (1.00, 1.6, 0.40),
    "M2.5": (1.25, 2.05, 0.45),
    "M3":   (1.50, 2.5, 0.50),
    "M4":   (2.00, 3.3, 0.70),
    "M5":   (2.50, 4.2, 0.80),
    "M6":   (3.00, 5.0, 1.00),
}


def _lookup(thread: ThreadSpec) -> tuple[float, float, float]:
    try:
        return _TABLE[thread]
    except KeyError:
        valid = ", ".join(sorted(_TABLE))
        raise ValueError(
            f"Unknown thread spec {thread!r}. Known: {valid}."
        ) from None


def major_radius(thread: ThreadSpec) -> float:
    """Thread major radius (mm) — outer cylinder of the male thread."""
    return _lookup(thread)[0]


def major_diameter(thread: ThreadSpec) -> float:
    """Thread major diameter (mm) — 2 × major_radius."""
    return 2 * _lookup(thread)[0]


def tap_drill_diameter(thread: ThreadSpec) -> float:
    """Tap-drill diameter (mm) — diameter the bore is drilled to before tapping."""
    return _lookup(thread)[1]


def tap_drill_radius(thread: ThreadSpec) -> float:
    """Tap-drill radius (mm) — tap_drill_diameter / 2."""
    return _lookup(thread)[1] / 2


def pitch(thread: ThreadSpec) -> float:
    """Coarse thread pitch (mm)."""
    return _lookup(thread)[2]


def known_threads() -> tuple[str, ...]:
    """Sorted tuple of every supported thread spec."""
    return tuple(sorted(_TABLE))


__all__ = [
    "ThreadSpec",
    "known_threads",
    "major_diameter",
    "major_radius",
    "pitch",
    "tap_drill_diameter",
    "tap_drill_radius",
]
