"""
Full purfling-cutter assembly.

Positions every part in the shank's frame so the STEP exports as a
single complete cutter. Joint-based kinematic assembly (proper
build123d Joints) is a future refinement; this draft uses plain
transforms with parts in a static "as-clamped" position:

  - Shaft centred through the crossbore at a nominal edge-margin.
  - Blade stack inside the slot, grub screw clamped against the stack.
  - Drive plate mounted on the shaft's −X end face.
  - Captive-screw + thumbwheel/drive screw forming the captive bearing
    at the shank's tapped-bore level.
  - Depth-lock bolt fully advanced, push rod pressing up on the
    shaft's −Z flat.

Coordinate frame is the shank's frame:
  X = along the shaft (perpendicular to working face)
  Y = perpendicular (tool-travel direction)
  Z = along the shank, vertical (+Z = top)
"""

from build123d import Compound, Pos

from gramil.parameters import PurflingCutterParams
from gramil.parts.blade import build_blade
from gramil.parts.blade_retainer import build_blade_retainer
from gramil.parts.captive_screw import build_captive_screw
from gramil.parts.channel_spacer import build_channel_spacer
from gramil.parts.depth_lock_bolt import build_depth_lock_bolt
from gramil.parts.drive_plate import build_drive_plate
from gramil.parts.grub_screw import build_grub_screw
from gramil.parts.mount_screw import build_mount_screw
from gramil.parts.push_rod import build_push_rod
from gramil.parts.shaft import build_shaft
from gramil.parts.shank import build_shank
from gramil.parts.thumbwheel_drive_screw import build_thumbwheel_drive_screw
from gramil.parts.washer import build_washer


def build_assembly(
    params: PurflingCutterParams,
    explode: float = 0.0,
    shaft_x_offset: float = 0.0,
    blade_drop_below_retainers: float | None = None,
) -> Compound:
    """Compose the full assembly as a single Compound.

    Args:
        params: cutter parameters.
        explode: explosion factor. 0 = fully assembled (default); 1.0 = each
            part translated outward by its natural disassembly direction by
            the per-part distance below. Use values in 0–1.5 typically.
        shaft_x_offset: X translation applied to the shaft + everything that
            moves with it (blade stack, grub screw, drive plate, captive
            screw, mount screw, thumbwheel/drive screw). 0 = centred through
            the crossbore (default). Positive values push the cutter end
            (+X) further out the working-face side of the shank.
        blade_drop_below_retainers: how far the blade tip protrudes below
            the bottom of the retainers. None (default) preserves the
            current behaviour (blade Z = crossbore_z − 2.5). When set,
            positions the blade Z so the tip sits at retainer_bottom_Z minus
            this value.
    """
    sp = params.shank
    crossbore_z = sp.length - sp.crossbore_position_from_top
    tapped_z = sp.length - params.tapped_bore_position_from_top

    # Explosion offsets (mm at explode=1.0). Each part shifts outward along
    # its natural disassembly direction. The shank stays as the anchor.
    EX_SHAFT = (25, 0, 0)
    EX_STACK = (25, 0, 0)         # blades + retainers + spacer move with shaft
    EX_GRUB = (55, 0, 0)
    EX_PLATE = (-25, 0, 0)
    EX_CAPTIVE = (-55, 0, 0)
    EX_WASHER = (-45, 0, 0)
    EX_TW = (-25, 0, 0)
    EX_BOLT = (0, 0, -35)
    EX_ROD = (0, 0, -15)

    def ex(direction: tuple[float, float, float]) -> tuple[float, float, float]:
        return (direction[0] * explode, direction[1] * explode, direction[2] * explode)

    shank = build_shank(params)

    # --- Shaft: centred through the crossbore (+ optional offset) -------
    shaft_local = build_shaft(params)
    shaft_len = params.shaft.length
    shaft_x_off = -shaft_len / 2 + shaft_x_offset
    ex_shaft = ex(EX_SHAFT)
    shaft = Pos(shaft_x_off + ex_shaft[0], ex_shaft[1], crossbore_z + ex_shaft[2]) * shaft_local

    # --- Blade slot stack (along the slot's X direction) ----------------
    slot_x_min = shaft_x_off + shaft_len - params.shaft.end_to_slot_distance - params.shaft.blade_slot_width
    blade_t = params.blade.thickness
    spacer_t = params.spacer.thickness
    ret_t = params.blade_retainer.thickness

    # Blade Z position. Default behaviour: blade Z = crossbore_z − 2.5
    # (legacy "as clamped" position). When blade_drop_below_retainers is
    # given, position the blade so its tip sits `drop` below the bottom of
    # the retainers. Retainer extends ±retainer.length/2 about crossbore_z.
    if blade_drop_below_retainers is None:
        blade_z = crossbore_z - 2.5
    else:
        retainer_bottom_z = crossbore_z - params.blade_retainer.length / 2
        # Blade is positioned by its centre Z; tip = blade_z − blade.length/2
        blade_tip_z = retainer_bottom_z - blade_drop_below_retainers
        blade_z = blade_tip_z + params.blade.length / 2

    retainer_local = build_blade_retainer(params)
    blade_local = build_blade(params)

    ex_stack = ex(EX_STACK)
    stack: list[Compound] = []
    x_c = slot_x_min
    for _ in range(2):
        stack.append(
            Pos(x_c + ret_t / 2 + ex_stack[0], ex_stack[1], crossbore_z + ex_stack[2])
            * retainer_local
        )
        x_c += ret_t
    stack.append(
        Pos(x_c + blade_t / 2 + ex_stack[0], ex_stack[1], blade_z + ex_stack[2]) * blade_local
    )
    x_c += blade_t
    if spacer_t > 0:
        spacer_local = build_channel_spacer(params)
        stack.append(
            Pos(x_c + spacer_t / 2 + ex_stack[0], ex_stack[1], blade_z + ex_stack[2])
            * spacer_local
        )
        x_c += spacer_t
    stack.append(
        Pos(x_c + blade_t / 2 + ex_stack[0], ex_stack[1], blade_z + ex_stack[2]) * blade_local
    )
    x_c += blade_t
    for _ in range(2):
        stack.append(
            Pos(x_c + ret_t / 2 + ex_stack[0], ex_stack[1], crossbore_z + ex_stack[2])
            * retainer_local
        )
        x_c += ret_t

    # --- Grub screw: tip touching the outboard end of the stack ---------
    grub_local = build_grub_screw(params)
    ex_grub = ex(EX_GRUB)
    grub = Pos(x_c + ex_grub[0], ex_grub[1], crossbore_z + ex_grub[2]) * grub_local

    # --- Drive plate: back face at shaft's −X end -----------------------
    # Note: drive plate, captive screw, mount screw and thumbwheel all move
    # with the shaft (they're captive to it through the captive bearing) —
    # shaft_x_off already carries shaft_x_offset.
    plate_local = build_drive_plate(params)
    plate_thick = params.drive_plate.thickness
    plate_x = shaft_x_off - plate_thick / 2
    ex_plate = ex(EX_PLATE)
    plate = Pos(plate_x + ex_plate[0], ex_plate[1], crossbore_z + ex_plate[2]) * plate_local

    # --- Thumbwheel/drive screw: journal bearing -------------------------
    # The boss face sits flush at the plate's back face; the integral journal
    # projects through the plate's bearing hole and is capped by a washer +
    # retaining screw clamped on the journal end face.
    tw_local = build_thumbwheel_drive_screw(params)
    tw_x = shaft_x_off  # boss face flush at the plate back face / shaft −X end
    ex_tw = ex(EX_TW)
    tw = Pos(tw_x + ex_tw[0], ex_tw[1], tapped_z + ex_tw[2]) * tw_local

    journal_end_x = tw_x - params.bearing_journal_length  # −X end of the journal

    # --- Retaining washer: on the journal end ----------------------------
    washer_local = build_washer(params)
    washer_t = params.captive_washer.thickness
    ex_wash = ex(EX_WASHER)
    washer = Pos(
        journal_end_x - washer_t / 2 + ex_wash[0], ex_wash[1], tapped_z + ex_wash[2]
    ) * washer_local

    # --- Captive (retaining) screw: head clamps the washer on journal end -
    captive_local = build_captive_screw(params)
    head_t = params.captive_screw.head_thickness
    captive_x = journal_end_x - washer_t - head_t  # local X=0 (head −X face)
    ex_captive = ex(EX_CAPTIVE)
    captive = Pos(captive_x + ex_captive[0], ex_captive[1], tapped_z + ex_captive[2]) * captive_local

    # --- Mount screw: through the plate centre into the shaft end tap -----
    mount_local = build_mount_screw(params)
    mount_head_t = params.mount_screw.head_thickness
    mount_x = plate_x - plate_thick / 2 - mount_head_t  # head −X face
    mount = Pos(mount_x + ex_captive[0], ex_captive[1], crossbore_z + ex_captive[2]) * mount_local

    # --- Depth-lock bolt + push rod (fully advanced) --------------------
    rod_local = build_push_rod(params)
    bolt_local = build_depth_lock_bolt(params)

    # Push rod top bears on the shaft's −Z flat
    rod_top_z = crossbore_z - params.shaft_outer_diameter / 2 + params.shaft.flat_depth
    rod_bottom_z = rod_top_z - params.push_rod_length
    ex_rod = ex(EX_ROD)
    rod = Pos(ex_rod[0], ex_rod[1], rod_bottom_z + ex_rod[2]) * rod_local

    # Bolt tip at rod bottom; bolt's local Z=knob+collar+thread is at the tip
    bolt_tip_local_z = (
        params.depth_lock.knob_thickness
        + params.depth_lock.bolt_collar_length
        + params.depth_lock.bolt_thread_length
    )
    ex_bolt = ex(EX_BOLT)
    bolt = Pos(ex_bolt[0], ex_bolt[1], rod_bottom_z - bolt_tip_local_z + ex_bolt[2]) * bolt_local

    # Each part named as the CNC package numbers it, the stock ones by their size, so the STEP
    # carries the names (build123d writes a shape's label as its product's name) and a reader
    # can tell the parts apart and the bought ones from those to make.
    g, c, m = params.grub_screw, params.captive_screw, params.mount_screw
    names = {
        id(shank): "GRM-01 shank",
        id(shaft): "GRM-02 shaft",
        id(tw): "GRM-03 thumbwheel drive screw",
        id(plate): "GRM-04 drive plate",
        id(bolt): "GRM-05 depth-lock bolt",
        id(grub): f"grub screw {g.thread}x{g.length:g}",
        id(captive): f"pan-head screw {c.thread}x{c.thread_length:g}",
        id(mount): f"pan-head screw {m.thread}x{m.thread_length:g}",
        id(washer): f"flat washer {c.thread}",
        id(rod): "push rod",
    }
    for part in stack:
        names[id(part)] = (
            "GRM-06 blade retainer" if part.wrapped.IsPartner(retainer_local.wrapped)
            else "GRM-07 blade" if part.wrapped.IsPartner(blade_local.wrapped)
            else "channel spacer"
        )
    children = [shank, shaft, *stack, grub, plate, washer, captive, mount, tw, bolt, rod]
    for part in children:
        part.label = names[id(part)]
    return Compound(children=children)


def main() -> None:
    """CLI: build the assembly and export STEP to /tmp/assembly.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    assembly = build_assembly(params)
    export_step(assembly, "/tmp/assembly.step")
    print(f"Exported /tmp/assembly.step  (volume = {assembly.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
