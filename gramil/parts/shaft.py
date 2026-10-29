"""
Shaft — brass bar passing horizontally through the shank's crossbore,
carrying the blades at its outboard end.

Coordinate convention (matches the shank — Z-up):
  X: along the shaft. +X = right end (carries the blade slot, near
     the workpiece). −X = left end (outboard, drive-plate end).
  Y: perpendicular to shaft, horizontal (tool-travel direction).
  Z: vertical (depth-of-cut direction). Blades drop down in −Z.

Features:
  - Round cross-section of diameter ``params.shaft_outer_diameter``
    (derived from ``cutting_pair.nominal_diameter``).
  - Flat machined on the underside (−Z) over a central X span — the
    depth-lock push rod registers against this flat.
  - Blade slot near the +X end: open through Z, with X extent =
    blade_slot_width and Y extent = blade_slot_length.
  - Grub-screw end tap (smooth bore at tap-drill diameter for now)
    in the +X end face, along X.
  - Two tapped holes in the −X end face (for the drive plate),
    spaced in Z, along X.

Threads on the grub-screw tap and the drive-plate mount holes come
later — this draft just leaves smooth bores at tap-drill diameter.
"""

from build123d import (
    Axis,
    Box,
    Cylinder,
    GeomType,
    Part,
    Pos,
    Rot,
    SortBy,
)

from gramil import threads
from gramil.parameters import PurflingCutterParams


def build_shaft(params: PurflingCutterParams) -> Part:
    """Build the shaft as a build123d Part."""
    shaft = params.shaft
    length = shaft.length
    od = params.shaft_outer_diameter
    radius = od / 2

    # --- Main cylinder along X --------------------------------------------
    # Default Cylinder is along Z; Rot(0, 90, 0) rotates Z → X. Wrap in Part()
    # so `body` is a plain Part, not a Cylinder instance — otherwise .chamfer()
    # below tries to rebuild a Cylinder (which needs a height arg) and throws.
    body = Part() + Pos(length / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=radius, height=length)

    # --- Chamfer the +X end OD corner (the grub-screw / blade end) ---------
    # Done HERE, before the flat/slot/bore cuts, so it's a clean full-circle
    # cone. Chamfering the flatted arc later caps out ~1.1 mm; on the full
    # circle the only limit is the grub bore (chamfer inner edge must stay
    # outside it), so larger chamfers build cleanly.
    if shaft.end_chamfer > 0:
        try:
            end_face = body.faces().sort_by(Axis.X).last
            rim = end_face.edges().filter_by(GeomType.CIRCLE).sort_by(SortBy.RADIUS).last
            body = body.chamfer(shaft.end_chamfer, None, [rim])  # type: ignore[assignment]
        except Exception:
            pass  # leave un-chamfered if the edge can't be resolved

    # --- Flat on the −Z underside, full length ----------------------------
    # Subtract a slab that covers the lower portion of the cylinder along the
    # full shaft length. The slab's +Z face sits at Z = −radius + flat_depth,
    # so the resulting flat surface is that height above the cylinder's bottom.
    flat_z_high = -radius + shaft.flat_depth
    flat_slab_height = radius * 3 + shaft.flat_depth
    flat_z_centre = flat_z_high - flat_slab_height / 2
    flat_x_extent = length + 4  # overshoot the ends so the cut goes fully through
    flat = Pos(length / 2, 0, flat_z_centre) * Box(
        flat_x_extent,
        radius * 4,
        flat_slab_height,
    )
    body = body - flat  # type: ignore[assignment]

    # --- Blade slot at the +X end -----------------------------------------
    # Slot's right wall (+X side) sits `end_to_slot_distance` from the +X end
    # face; slot extends inward (−X) for `blade_slot_width`. Open through Z
    # so blades drop in from the top and project out the bottom.
    slot_x_max = length - shaft.end_to_slot_distance
    slot_x_min = slot_x_max - shaft.blade_slot_width
    slot_x_centre = (slot_x_min + slot_x_max) / 2
    slot = Pos(slot_x_centre, 0, 0) * Box(
        shaft.blade_slot_width,
        shaft.blade_slot_length,
        radius * 4,  # through Z, generously beyond the shaft's vertical extent
    )
    body = body - slot  # type: ignore[assignment]

    # --- Grub-screw end tap (smooth bore) in the +X end face --------------
    # Tap goes ALL THE WAY to the slot — no wall in between. So the tap
    # depth equals end_to_slot_distance; the grub screw's tip emerges into
    # the slot and directly contacts the blade stack.
    grub_thread = params.grub_screw.thread
    grub_drill_radius = threads.tap_drill_radius(grub_thread)
    end_tap_depth = shaft.end_to_slot_distance
    end_tap = (
        Pos(length - end_tap_depth / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(radius=grub_drill_radius, height=end_tap_depth)
    )
    body = body - end_tap  # type: ignore[assignment]

    # --- Anti-rotation slot in the −X end face ----------------------------
    # A *horizontal slot* cut into the shaft's −X end face, milled across
    # the full diameter (one mill pass). Receives the matching tenon on
    # the drive plate's back face. Combined with the single central M2
    # mount screw, the slot prevents rotation of the plate relative to
    # the shaft.
    tenon_depth = params.drive_plate.tenon_depth
    tenon_height = params.drive_plate.tenon_height
    overshoot = 0.5  # opens the slot cleanly through the end face and side
    slot_x_size = tenon_depth + overshoot
    slot_x_centre = -overshoot / 2 + tenon_depth / 2  # spans −overshoot to +tenon_depth
    end_slot = Pos(slot_x_centre, 0, 0) * Box(
        slot_x_size,
        od + 2 * overshoot,  # wider than shaft so the cut goes clean through Y
        tenon_height,
    )
    body = body - end_slot  # type: ignore[assignment]

    # --- Drive-plate mount hole in the −X end face ------------------------
    # Single central tapped hole. Two M2 screws don't fit on a 7.9 mm shaft,
    # so we use one + the slot for anti-rotation (see above).
    mount_thread = shaft.drive_plate_mount_thread
    mount_drill_radius = threads.tap_drill_radius(mount_thread)
    mount_depth = shaft.drive_plate_mount_depth
    mount_hole = (
        Pos(mount_depth / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(radius=mount_drill_radius, height=mount_depth)
    )
    body = body - mount_hole  # type: ignore[assignment]

    return body


def main() -> None:
    """CLI: build the shaft with default params and export STEP to /tmp/shaft.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    shaft = build_shaft(params)
    export_step(shaft, "/tmp/shaft.step")
    print(f"Exported /tmp/shaft.step  (volume = {shaft.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
