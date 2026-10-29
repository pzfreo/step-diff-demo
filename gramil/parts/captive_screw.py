"""
Captive (retaining) screw — the small stock M2 fastener for the journal
bearing. It threads into the deep tap down the bearing journal's centre and
clamps the retaining washer against the journal end face. The bearing axial
play is set by the journal length (not by this screw), so the screw can be
torqued fully.

Local frame:
  X: along the screw axis. X = 0 = head's outboard (−X) face;
     +X = inboard (toward the thumbwheel).
"""

from build123d import (
    Cylinder,
    Part,
    Pos,
    Rot,
)

from gramil import threads
from gramil.parameters import PurflingCutterParams


def build_captive_screw(params: PurflingCutterParams) -> Part:
    """Build the captive (retaining) screw — stock M2, thread length from the
    CaptiveScrewParams field. It clamps the washer on the journal end; the
    journal tap is cut deeper than the thread so the head seats positively."""
    cs = params.captive_screw

    head_d = cs.head_diameter
    head_t = cs.head_thickness
    thread_r = threads.major_radius(cs.thread)
    thread_len = cs.thread_length

    # Head: cylinder along X at X = head_t / 2
    head = Pos(head_t / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=head_d / 2, height=head_t)
    # Thread: cylinder along X starting at X = head_t, extending to X = head_t + thread_len
    thread = (
        Pos(head_t + thread_len / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(radius=thread_r, height=thread_len)
    )

    body = head + thread
    return body  # type: ignore[return-value]


def main() -> None:
    from build123d import export_step

    params = PurflingCutterParams()
    screw = build_captive_screw(params)
    export_step(screw, "/tmp/captive_screw.step")
    print(f"Exported /tmp/captive_screw.step  (volume = {screw.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
