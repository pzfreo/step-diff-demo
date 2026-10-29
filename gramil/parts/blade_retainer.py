"""
Bone-shaped copper retainer. Four per tool, sit in the blade slot to
hold the blade-spacer-blade stack in place along the slot's X direction.

Local frame:
  X: thickness (0.85 mm). Plate's normal direction.
  Y: width — varies along the bone profile: 5.5 mm at the ends, 4.3 mm
     in the middle.
  Z: long axis (10 mm). Bone profile is symmetric about Z = 0.

Three stacked rectangles (top knob + waist + bottom knob), then two
sets of fillets:
  - outermost knob tips (|Y|=end_w/2, |Z|=L/2)
  - shoulder corners that 'stick out' from the waist outline
    (|Y|=end_w/2, |Z|=mid_z/2)
"""

from build123d import Axis, Box, Part, Pos

from gramil.parameters import PurflingCutterParams


def build_blade_retainer(params: PurflingCutterParams) -> Part:
    """Build one bone-shaped retainer."""
    r = params.blade_retainer
    t = r.thickness
    end_w = r.end_width
    mid_w = r.middle_width
    L = r.length
    mid_z = r.middle_length
    end_z = (L - mid_z) / 2
    fillet_r = r.corner_fillet_radius
    shoulder_r = r.shoulder_fillet_radius

    top_end = Pos(0, 0, +(L / 2 - end_z / 2)) * Box(t, end_w, end_z)
    middle = Pos(0, 0, 0) * Box(t, mid_w, mid_z)
    bot_end = Pos(0, 0, -(L / 2 - end_z / 2)) * Box(t, end_w, end_z)

    body: Part = top_end + middle + bot_end  # type: ignore[assignment]

    # Fillet the four outside corners of the bone — the X-direction edges at
    # |Y| = end_w/2 AND |Z| = L/2 (the outermost corners of each knob).
    if fillet_r > 0:
        tol = 0.05
        outside_corner_edges = [
            e
            for e in body.edges().filter_by(Axis.X)
            if abs(abs(e.center().Y) - end_w / 2) < tol
            and abs(abs(e.center().Z) - L / 2) < tol
        ]
        if outside_corner_edges:
            body = body.fillet(fillet_r, outside_corner_edges)  # type: ignore[assignment]

    # Fillet the four shoulder corners — the convex X-direction edges where
    # each knob steps inward to the waist on the outer ±Y face. These are
    # the corners that 'stick out' from the waist outline.
    if shoulder_r > 0:
        tol = 0.05
        shoulder_edges = [
            e
            for e in body.edges().filter_by(Axis.X)
            if abs(abs(e.center().Y) - end_w / 2) < tol
            and abs(abs(e.center().Z) - mid_z / 2) < tol
        ]
        if shoulder_edges:
            body = body.fillet(shoulder_r, shoulder_edges)  # type: ignore[assignment]

    return body


def main() -> None:
    from build123d import export_step

    params = PurflingCutterParams()
    retainer = build_blade_retainer(params)
    export_step(retainer, "/tmp/blade_retainer.step")
    print(f"Exported /tmp/blade_retainer.step  (volume = {retainer.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
