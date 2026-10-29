"""
Grub screw — threaded into the shaft's +X end tap to clamp the
blade-spacer-blade-retainers stack.

Local frame:
  X: along the screw axis. X = 0 = +X (outer) face; +X points inboard.

Modelled as a plain cylinder at the thread's major diameter, length =
grub_screw.length. Slot / hex drive head not modelled.
"""

from build123d import Cylinder, Part, Pos, Rot

from gramil import threads
from gramil.parameters import PurflingCutterParams


def build_grub_screw(params: PurflingCutterParams) -> Part:
    """Build the grub screw."""
    gs = params.grub_screw
    radius = threads.major_radius(gs.thread)
    body: Part = Pos(gs.length / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=radius, height=gs.length)
    return body


def main() -> None:
    from build123d import export_step

    params = PurflingCutterParams()
    screw = build_grub_screw(params)
    export_step(screw, "/tmp/grub_screw.step")
    print(f"Exported /tmp/grub_screw.step  (volume = {screw.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
