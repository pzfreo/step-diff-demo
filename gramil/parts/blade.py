"""
Blade — one of the two flat tool-steel cutters in the shaft's blade slot.

Local frame (the natural blade frame):
  X: thickness direction (0.7 mm). Wide flat face is perpendicular to X.
     +X = bevel face (ground side). −X = flat back (registers against
     the spacer / next blade). The cutting edge runs along the tip
     outline at X = −t/2 (where the flat bevel meets the flat back).
  Y: width direction (3.6 mm). The blade's "narrow" face.
  Z: length direction (23 mm). +Z = top (where the blade drops into the
     slot from), −Z = tip (cuts the violin).

Geometry:
  - Rectangular shank for the upper portion.
  - Semicircular tip cap (radius = width/2).
  - Single bevel ground at the tip — modelled as a flat-plane wedge
    subtracted from the rounded end. The wedge is a triangular prism
    in the XZ plane extruded along Y, with vertices:
        (X=−t/2, Z=−L/2)              — the very tip (cutting edge)
        (X=+t/2, Z=−L/2)              — the +X side of the bottom
        (X=+t/2, Z=−L/2 + bevel_run)  — the heel on the +X face
    where bevel_run = t / tan(bevel_angle).
    The wedge lies entirely within the tip region (its top vertex
    sits at Z = −L/2 + bevel_run ≈ Z=−10 for the default geometry —
    well below the rectangular section's −Z bottom at Z=−L/2 + w/2 =
    −9.7), so the rectangular cross-section above the rounded tip
    is preserved.
"""

import math

from build123d import (
    Box,
    BuildLine,
    BuildSketch,
    Cylinder,
    Line,
    Part,
    Plane,
    Pos,
    Rot,
    extrude,
    make_face,
)

from gramil.parameters import PurflingCutterParams


def build_blade(params: PurflingCutterParams) -> Part:
    """Build a single blade with a single-bevel ground tip."""
    blade = params.blade
    t = blade.thickness
    w = blade.width
    L = blade.length
    bevel_angle = blade.bevel_angle

    # Rectangular shank for the upper portion of the blade.
    box_len_z = L - w / 2
    box = Pos(0, 0, w / 4) * Box(t, w, box_len_z)

    # Semicircular tip cap — cylinder along X with radius = w/2.
    tip = (
        Pos(0, 0, -L / 2 + w / 2) * Rot(0, 90, 0) * Cylinder(radius=w / 2, height=t)
    )

    body: Part = box + tip  # type: ignore[assignment]

    # Single bevel grind — subtract a triangular-prism wedge in the XZ plane
    # extruded along Y. The wedge bottoms at Z=-L/2 (tip) and tops at
    # Z=-L/2 + bevel_run on the +X side. bevel_run = t / tan(bevel_angle).
    if bevel_angle > 0:
        bevel_run = t / math.tan(math.radians(bevel_angle))
        tip_z = -L / 2
        with BuildSketch(Plane.XZ) as wedge_sketch:
            with BuildLine():
                Line((-t / 2, tip_z), (t / 2, tip_z))
                Line((t / 2, tip_z), (t / 2, tip_z + bevel_run))
                Line((t / 2, tip_z + bevel_run), (-t / 2, tip_z))
            make_face()
        wedge = extrude(wedge_sketch.sketch, amount=w / 2 + 1, both=True)
        body = body - wedge  # type: ignore[assignment]

    return body


def main() -> None:
    """CLI: export blade to /tmp/blade.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    blade = build_blade(params)
    export_step(blade, "/tmp/blade.step")
    print(f"Exported /tmp/blade.step  (volume = {blade.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
