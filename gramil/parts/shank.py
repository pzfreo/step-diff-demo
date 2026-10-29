"""
Shank — the square brass body that doubles as the fence.

Coordinate convention (Z-up, intuitive for holding the tool):
  Z: along the shank, +Z = top (drive screw / thumbwheel end).
     Bottom of shank (depth-lock knob) at Z = 0.
  X: along the shaft AND normal to the working face. +X = working face
     direction. The shaft passes through the working face out toward the
     workpiece. Edge-margin adjustment translates the shaft in X.
  Y: perpendicular to both. Tool-travel direction (along the violin edge).

Blades cut downward in −Z when the tool is in use.

This draft uses *smooth* bores (no thread geometry yet) and a single
fillet radius applied to all external edges as the finishing layer.
"""

from build123d import (
    Align,
    Box,
    Cylinder,
    Part,
    Pos,
    Rot,
    Sphere,
)

from gramil.parameters import PurflingCutterParams
from gramil.parts._threads import internal_thread_cutout


def build_shank(params: PurflingCutterParams) -> Part:
    """Build the shank as a build123d Part, using `params` as single source of truth."""
    shank = params.shank
    length = shank.length  # Z extent
    width = shank.width  # X extent (perpendicular to working face)
    depth = shank.depth  # Y extent (tool-travel direction)

    # Box: X width centered, Y depth centered, Z length from 0 (bottom) to length (top).
    # Working face is +X face at X = +width/2. Wrap in Part() so subsequent
    # boolean ops (and fillet) produce a Part-compatible result rather than
    # trying to instantiate a new Box from the modified shape.
    body: Part = Part() + Box(width, depth, length, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # --- Ergonomic fillet on the Box BEFORE curved features ---------------
    # OCCT cannot reliably fillet all edges of the final shape (convex
    # face + spherical dome + bores creates edge configurations that the
    # filleting algorithm gives up on). The fix is to round the simple Box
    # first: 1 mm fillet on all 12 edges. The subsequent convexity-intersect
    # replaces the front-side filleted edges with the smooth convex curve;
    # the dome intersect replaces the top edges with the dome surface;
    # and the bore + slot cuts come last so those edges remain sharp.
    fillet_r = shank.edge_fillet_radius
    if fillet_r > 0:
        body = body.fillet(fillet_r, body.edges())

    # --- Convex working face (+X face) ------------------------------------
    # The +X face is curved so the centre of Y bulges out in +X. Intersect
    # the box with a cylinder whose axis runs along Z at (width/2 − R, 0).
    # At Y = 0 the cylinder surface sits at X = width/2 (the peak); at
    # Y = ±depth/2 it sits inboard, trimming the +X corners.
    radius = shank.working_face_radius
    convexity_cyl = (
        Pos(width / 2 - radius, 0, length / 2) * Cylinder(radius=radius, height=length + 20)
    )
    body = body & convexity_cyl

    # --- Spherical dome at the top (+Z end) -------------------------------
    # The +Z face of the shank is a sphere section, rounded in both X and Y.
    # Surface tangents the original top face at the centre (X = 0, Y = 0,
    # Z = length); at off-centre X or Y, the sphere dips below Z = length,
    # trimming the box's top corners.
    dome_r = shank.top_dome_radius
    top_sphere = Pos(0, 0, length - dome_r) * Sphere(radius=dome_r)
    big = max(length, width, depth) * 4
    lower_zone = Pos(0, 0, (length - dome_r) / 2) * Box(big, big, length - dome_r)
    body = body & (lower_zone + top_sphere)

    # --- Relief slot in the working face ----------------------------------
    # Length along Z (shank long axis), width across Y, depth into −X.
    # Cut box extends past +X by slot_overdepth so it cuts through whatever
    # convexity is left at the bottom of the slot.
    slot_overdepth = 2.0
    slot_x_min = width / 2 - shank.relief_slot_depth
    slot_x_max = width / 2 + slot_overdepth
    slot_x_extent = slot_x_max - slot_x_min
    slot_x_centre = (slot_x_min + slot_x_max) / 2
    slot_length = params.relief_slot_length
    slot = Pos(slot_x_centre, 0, slot_length / 2) * Box(
        slot_x_extent,
        shank.relief_slot_width,
        slot_length,
    )
    body = body - slot

    # --- Crossbore (along X — the shaft direction) ------------------------
    crossbore_z = length - shank.crossbore_position_from_top
    crossbore = (
        Pos(0, 0, crossbore_z)
        * Rot(0, 90, 0)
        * Cylinder(radius=params.crossbore_diameter / 2, height=width + 20)
    )
    body = body - crossbore

    # --- Shank tapped bore (along X) --------------------------------------
    # FDM prototype path: subtract a void shape = (clearance bore at thread
    # major) minus (helical thread ribs), giving a real tapped bore in one
    # boolean. CNC path: plain bore at tap-drill diameter — the shop reads
    # the thread spec off the drawing.
    tapped_z = length - params.tapped_bore_position_from_top
    if params.process.prototype:
        tapped_cutout = (
            Pos(-width / 2, 0, tapped_z)
            * Rot(0, 90, 0)
            * internal_thread_cutout(params.drive_screw.thread, width)
        )
        body = body - tapped_cutout
    else:
        tapped = (
            Pos(0, 0, tapped_z)
            * Rot(0, 90, 0)
            * Cylinder(radius=params.tapped_bore_drill_diameter / 2, height=width + 20)
        )
        body = body - tapped

    # --- Depth-lock blind bore (along Z, from Z = 0 up) -------------------
    # Stack from bottom: collar bore (smooth, slightly larger than the bolt
    # thread OD) → M6-tapped section → smooth bore for the push rod.
    dl_depth = params.depth_lock_bore_depth
    dl_radius = shank.depth_lock_bore_diameter / 2
    dl_collar_r = shank.depth_lock_collar_bore_diameter / 2
    dl_collar_len = shank.depth_lock_collar_bore_length
    dl_thread_len = shank.depth_lock_threaded_length
    dl_upper_z_start = dl_collar_len + dl_thread_len
    dl_upper_len = dl_depth - dl_upper_z_start

    collar_bore = Pos(0, 0, dl_collar_len / 2) * Cylinder(
        radius=dl_collar_r, height=dl_collar_len
    )
    body = body - collar_bore

    if params.process.prototype:
        # Push-rod sliding fit, above the tapped section.
        upper_bore = Pos(0, 0, dl_upper_z_start + dl_upper_len / 2) * Cylinder(
            radius=dl_radius, height=dl_upper_len
        )
        body = body - upper_bore
        # Tapped section between collar bore and push-rod bore.
        thread_cutout = Pos(0, 0, dl_collar_len) * internal_thread_cutout(
            params.depth_lock.thread, dl_thread_len
        )
        body = body - thread_cutout
    else:
        # CNC path: clean cylinder through the tap + push-rod sections.
        depth_lock_bore = Pos(0, 0, dl_collar_len + (dl_depth - dl_collar_len) / 2) * Cylinder(
            radius=dl_radius, height=dl_depth - dl_collar_len
        )
        body = body - depth_lock_bore

    return body


def main() -> None:
    """CLI: build the shank with default params and export STEP to /tmp/shank.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    shank = build_shank(params)
    export_step(shank, "/tmp/shank.step")
    print(f"Exported /tmp/shank.step  (volume = {shank.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
