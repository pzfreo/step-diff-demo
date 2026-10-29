"""
Drive plate — small brass plate that stands vertically up from the shaft's
outboard end, transmits drive screw translation to the shaft via the
captive-screw bearing at its thumb end.

Coordinate convention (plate's local frame):
  X: plate normal — thickness direction. +X = "back" (faces the shaft),
     −X = "front" (faces outboard, where the captive-screw head sits).
  Y: horizontal across the plate.
  Z: vertical. Origin (Z = 0) is the shaft-end boss centre; the thumb-end
     boss centre sits at Z = crossbore_to_tapped_bore_gap.

Outline: **egg shape** — larger circle (shaft_end_radius) at Z = 0,
smaller circle (thumb_end_radius) at Z = gap, connected by external
tangent lines.

Holes:
  - Central mount-screw clearance hole at the shaft end (Z = 0).
  - Captive-screw clearance hole at the thumb end (Z = gap).

Anti-rotation: small rectangular tenon projecting from the back face
(+X face) at Z = 0, sized to engage a matching slot in the shaft's
−X end face. The tenon + slot pair prevents the plate from rotating
around the mount-screw axis; the screw itself holds the parts axially.
The tenon is on the plate (not the shaft) so the plate keeps full
thickness in the load-bearing region.
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


def build_drive_plate(params: PurflingCutterParams) -> Part:
    """Build the drive plate as a build123d Part."""
    dp = params.drive_plate
    r_big = dp.shaft_end_radius
    r_small = dp.thumb_end_radius
    gap = params.shank.crossbore_to_tapped_bore_gap
    thickness = dp.thickness

    # --- Egg outline ------------------------------------------------------
    # External tangent lines between two circles of different radii at a
    # given centre-to-centre distance. The tangent contact angle on the
    # large circle (measured from the line joining the centres) is:
    #     alpha = acos((r_big − r_small) / gap)
    alpha = math.acos((r_big - r_small) / gap)
    sin_a, cos_a = math.sin(alpha), math.cos(alpha)

    # Tangent points in the YZ sketch plane (local x = world Y, local y = world Z).
    p1_r = (r_big * sin_a, r_big * cos_a)  # right tangent on big circle
    p1_l = (-r_big * sin_a, r_big * cos_a)
    p2_r = (r_small * sin_a, gap + r_small * cos_a)  # right tangent on small
    p2_l = (-r_small * sin_a, gap + r_small * cos_a)

    # Two cylinders form the round ends; a quadrilateral filler with tangent
    # edges joins them smoothly.
    big = Pos(0, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=r_big, height=thickness)
    small = Pos(0, 0, gap) * Rot(0, 90, 0) * Cylinder(radius=r_small, height=thickness)

    with BuildSketch(Plane.YZ) as quad_sketch:
        with BuildLine():
            Line(p1_l, p1_r)
            Line(p1_r, p2_r)
            Line(p2_r, p2_l)
            Line(p2_l, p1_l)
        make_face()
    quad = extrude(quad_sketch.sketch, amount=thickness / 2, both=True)

    plate = big + small + quad

    # --- Anti-rotation tenon on the back face (+X face) -------------------
    # Boss projecting outboard from the back face at Z = 0. The tenon's Y
    # outline follows the plate's egg perimeter at the tenon's Z range — no
    # corners protruding past the plate edge. Built by extruding the same
    # egg outline by tenon_depth, then clipping to the tenon's Z band.
    tenon_x_centre = thickness / 2 + dp.tenon_depth / 2
    big_t = Pos(tenon_x_centre, 0, 0) * Rot(0, 90, 0) * Cylinder(
        radius=r_big, height=dp.tenon_depth
    )
    small_t = Pos(tenon_x_centre, 0, gap) * Rot(0, 90, 0) * Cylinder(
        radius=r_small, height=dp.tenon_depth
    )
    quad_t = extrude(quad_sketch.sketch, amount=dp.tenon_depth / 2, both=True).translate(
        (tenon_x_centre, 0, 0)
    )
    egg_extension = big_t + small_t + quad_t
    tenon_clipper = Pos(tenon_x_centre, 0, 0) * Box(
        dp.tenon_depth + 1, 2 * r_big + 2, dp.tenon_height
    )
    tenon = egg_extension & tenon_clipper
    plate = plate + tenon

    # --- Holes ------------------------------------------------------------
    # Mount hole at shaft end: standard M2 clearance (~0.2 mm radial). Goes
    # through the plate AND the tenon — the mount screw must reach the tap
    # in the shaft's end face past the tenon engagement.
    # Thumb-end hole: the journal BEARING hole — the plate rides on the
    # drive-screw's integral journal (journal ⌀ + running clearance).
    mount_r = dp.mount_hole_diameter / 2
    captive_r = params.plate_bearing_hole_diameter / 2
    mount_hole = (
        Pos(0, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=mount_r, height=thickness * 3)
    )
    captive_hole = (
        Pos(0, 0, gap) * Rot(0, 90, 0) * Cylinder(radius=captive_r, height=thickness * 3)
    )
    plate = plate - mount_hole - captive_hole

    return plate  # type: ignore[return-value]


def main() -> None:
    """CLI: build the drive plate and export STEP to /tmp/drive_plate.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    plate = build_drive_plate(params)
    export_step(plate, "/tmp/drive_plate.step")
    print(f"Exported /tmp/drive_plate.step  (volume = {plate.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
