"""
Depth-lock bolt + knurled knob — the M6 hand-clamp at the bottom of the
shank's depth-lock blind bore. The bolt's tip pushes the push rod up to
clamp the shaft against the underside of the cross-bore.

Local frame:
  Z: along the bolt axis. Z = 0 = bottom face of the knurled knob;
     +Z = upward (into the shank when assembled).

Stack from bottom (−Z) to top (+Z):
  Knob (knurled disc, knob_diameter × knob_thickness)
   → Collar (smooth, bolt_collar_diameter × bolt_collar_length)
   → M6 threaded portion (thread major diameter × bolt_thread_length)
   → Chamfered tip (bolt_tip_chamfer, 45°)

The collar mates with an enlarged section at the bottom of the shank's
depth-lock bore as an anti-cocking guide. The chamfer is a thread lead-in
to avoid cross-threading. Knurl decoration not modelled.
"""

from build123d import Axis, Cylinder, Part, Pos

from gramil import threads
from gramil.parameters import PurflingCutterParams
from gramil.parts._threads import external_thread_section


def build_depth_lock_bolt(params: PurflingCutterParams) -> Part:
    """Build the depth-lock bolt + knurled knob as one piece."""
    dl = params.depth_lock
    knob_r = dl.knob_diameter / 2
    knob_t = dl.knob_thickness
    collar_r = dl.bolt_collar_diameter / 2
    collar_len = dl.bolt_collar_length
    bolt_r = threads.major_radius(dl.thread)
    bolt_len = dl.bolt_thread_length
    chamfer = dl.bolt_tip_chamfer

    z_collar_start = knob_t
    z_thread_start = knob_t + collar_len

    knob = Pos(0, 0, knob_t / 2) * Cylinder(radius=knob_r, height=knob_t)
    collar = Pos(0, 0, z_collar_start + collar_len / 2) * Cylinder(
        radius=collar_r, height=collar_len
    )

    if params.process.prototype:
        bolt = Pos(0, 0, z_thread_start) * external_thread_section(dl.thread, bolt_len)
    else:
        bolt = Pos(0, 0, z_thread_start + bolt_len / 2) * Cylinder(
            radius=bolt_r, height=bolt_len
        )

    body = knob + collar + bolt

    # Lead-in chamfer on the +Z thread tip (CNC path only — real-thread
    # geometry on the prototype path already has tapered top turns).
    if chamfer > 0 and not params.process.prototype:
        try:
            top_face = body.faces().sort_by(Axis.Z).last
            top_edges = list(top_face.edges())
            body = body.chamfer(chamfer, None, top_edges)  # type: ignore[assignment]
        except Exception:
            pass  # leave un-chamfered if the boolean fails

    # Large chamfer on the knob's bottom edge (the hand-facing end of the
    # knurled wheel). Selected as the circular edge at the knob radius on
    # the −Z face.
    knob_chamfer = dl.knob_bottom_chamfer
    if knob_chamfer > 0:
        try:
            bottom_face = body.faces().sort_by(Axis.Z).first
            body = body.chamfer(knob_chamfer, None, list(bottom_face.edges()))  # type: ignore[assignment]
        except Exception:
            pass

    return body  # type: ignore[return-value]


def main() -> None:
    from build123d import export_step

    params = PurflingCutterParams()
    part = build_depth_lock_bolt(params)
    export_step(part, "/tmp/depth_lock_bolt.step")
    print(f"Exported /tmp/depth_lock_bolt.step  (volume = {part.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
