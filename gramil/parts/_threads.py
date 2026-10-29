"""
Helpers for building real ISO helical threads via bd_warehouse.IsoThread.

Only used on the **FDM prototype path** (process.prototype = True), where
the printed plastic mechanism has to physically engage. For the CNC
production path the parts stay as clean cylinders + drawing callouts —
that's the contract a machine shop reads, not the helical geometry.

Two helpers:
  - external_thread_section: a screw-shaft chunk (core cylinder + helix).
  - internal_thread_cutout: the *void* shape for a tapped bore — the
    clearance bore at thread major diameter minus the helical ribs.
    Caller subtracts this from the host part.

Both are built along +Z in their local frame; caller applies placement.
"""

from bd_warehouse.thread import IsoThread  # type: ignore[import-untyped]
from build123d import Cylinder, Part, Pos, Solid

from gramil import threads


def _fused_isothread(*, major_diameter: float, pitch: float, length: float, external: bool) -> Solid:
    """Build an IsoThread and fuse its per-turn solids into a single Solid.

    bd_warehouse returns one Solid per thread pitch turn. Booleans
    against a host body misbehave when that many separate solids are
    fed in, so we fuse them into one before returning.
    """
    helix = IsoThread(
        major_diameter=major_diameter, pitch=pitch, length=length, external=external
    )
    return Solid.fuse(*helix.solids())  # type: ignore[return-value]


def _thread_dims(thread: str) -> tuple[float, float]:
    """Return (major_diameter, pitch) for the named thread."""
    return threads.major_diameter(thread), threads.pitch(thread)


def external_thread_section(thread: str, length: float) -> Part:
    """
    Build a complete external-threaded section as a single Part.

    Core cylinder at the thread's minor radius + the helical thread
    fused on top. Z = 0 is the bottom face of the core; Z = length is
    the top.
    """
    major_d, pitch = _thread_dims(thread)
    helix = _fused_isothread(major_diameter=major_d, pitch=pitch, length=length, external=True)
    probe = IsoThread(major_diameter=major_d, pitch=pitch, length=pitch, external=True)
    core = Pos(0, 0, length / 2) * Cylinder(radius=probe.min_radius, height=length)
    section = core + helix
    return section  # type: ignore[return-value]


def internal_thread_cutout(thread: str, length: float) -> Part:
    """
    Build the void shape for a tapped bore: a cylinder at the thread's
    major diameter, minus the helical thread ribs that protrude inward.

    Caller subtracts this from the host part to get the tapped bore
    directly (no second fuse step needed, which avoids the boolean
    glitch where add-thread-to-host drops the host material).

    The cutout sits at Z ∈ [0, length]; X/Y centred on its axis.
    """
    major_d, pitch = _thread_dims(thread)
    bore = Pos(0, 0, length / 2) * Cylinder(radius=major_d / 2, height=length)
    ribs = _fused_isothread(major_diameter=major_d, pitch=pitch, length=length, external=False)
    cutout = bore - ribs
    return cutout  # type: ignore[return-value]
