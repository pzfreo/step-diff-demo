"""
Drive-plate mount screw — the small M2 fastener that holds the drive plate
to the shaft's −X end face. Passes through the plate's mount clearance
hole, through the tenon (which sits in the shaft's end slot), and threads
into the M2 tap on the shaft's end face.

Local frame:
  X: along the screw axis. X = 0 = head's outboard (−X) face;
     +X = inboard (toward the shaft).
"""

from build123d import (
    Cylinder,
    Part,
    Pos,
    Rot,
)

from gramil import threads
from gramil.parameters import PurflingCutterParams


def build_mount_screw(params: PurflingCutterParams) -> Part:
    """Build the drive-plate mount screw."""
    ms = params.mount_screw

    head_d = ms.head_diameter
    head_t = ms.head_thickness
    thread_r = threads.major_radius(ms.thread)
    thread_len = ms.thread_length

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
    screw = build_mount_screw(params)
    export_step(screw, "/tmp/mount_screw.step")
    print(f"Exported /tmp/mount_screw.step  (volume = {screw.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
