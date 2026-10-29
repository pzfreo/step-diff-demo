"""
Thumbwheel + drive screw — integral piece on the −X (outboard) side of the
shank. Spec §4.4 says these are turned from one piece.

Layout along X (from the −X outboard face at X = 0, inboard toward +X):

  boss | thumbwheel disc | unthreaded collar | M3 drive-screw thread

  X = 0                          (captive-screw tap entry; outboard −X face)
       boss_length
            + thumbwheel.thickness
                 + drive_screw.unthreaded_length
                      + drive_screw.length        (total = thread inboard end)

Bores:
  - Captive-screw tap from the −X face inward by left_face_tap_depth. With
    default values (boss 0.5, disc 2, unthreaded collar 3, tap depth 3) the
    tap bottoms 0.5 mm into the unthreaded collar — well before the M3
    thread root, so the captive-screw tap can never compromise the drive-
    screw thread.

The threaded portion is modelled as a smooth cylinder at the thread's
major diameter for now; real IsoThread geometry comes later.
"""

from dataclasses import dataclass

from build123d import (
    Axis,
    Cylinder,
    GeomType,
    Part,
    Pos,
    Rot,
)

from gramil import threads
from gramil.parameters import PurflingCutterParams
from gramil.parts._threads import external_thread_section


@dataclass
class ThumbwheelDriveScrewFeatures:
    """Named turned features retained for object-referenced drawings."""

    boss: Part
    disc: Part
    unthreaded: Part
    thread: Part
    journal: Part
    tap: Part
    body: Part


def build_thumbwheel_drive_screw_features(
    params: PurflingCutterParams,
) -> ThumbwheelDriveScrewFeatures:
    """Build the part while retaining each pre-union turned feature."""
    tw = params.thumbwheel
    ds = params.drive_screw

    # Section lengths along X
    boss_len = tw.boss_length
    disc_thick = tw.thickness
    unth_len = ds.unthreaded_length
    thread_len = ds.length

    # Radii
    boss_r = tw.boss_diameter / 2
    disc_r = tw.diameter / 2
    unth_r = ds.unthreaded_diameter / 2
    thread_r = threads.major_radius(ds.thread)

    # X centres for each section, stacked along +X
    x_boss = boss_len / 2
    x_disc = boss_len + disc_thick / 2
    x_unth = boss_len + disc_thick + unth_len / 2
    x_thread = boss_len + disc_thick + unth_len + thread_len / 2

    # Default Cylinder is along Z; Rot(0, 90, 0) rotates Z → X.
    boss = (
        Pos(x_boss, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=boss_r, height=boss_len)
    )
    disc = Pos(x_disc, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=disc_r, height=disc_thick)
    unthreaded = (
        Pos(x_unth, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=unth_r, height=unth_len)
    )

    # Drive-screw thread: real ISO helix on the FDM prototype path; plain
    # major-diameter cylinder on the CNC path (the shop reads the thread
    # callout off the drawing, not the geometry — see _threads.py docstring).
    thread_start_x = boss_len + disc_thick + unth_len
    if params.process.prototype:
        thread = Pos(thread_start_x, 0, 0) * Rot(0, 90, 0) * external_thread_section(
            ds.thread, thread_len
        )
    else:
        thread = (
            Pos(x_thread, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=thread_r, height=thread_len)
        )

    body: Part = boss + disc + unthreaded + thread  # type: ignore[assignment]

    # --- Integral bearing journal on the boss (−X) face -------------------
    # Turned stub the drive plate's thumb-end hole rides on; capped by a
    # washer + screw. The plate floats by `axial_play` on it (the journal is
    # machined that much longer than the plate is thick). The boss face (⌀6)
    # around the ⌀4 journal is the thrust shoulder.
    journal_r = ds.bearing_journal_diameter / 2
    journal_len = params.bearing_journal_length
    journal = (
        Pos(-journal_len / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=journal_r, height=journal_len)
    )
    body = body + journal

    # --- Captive-screw tap, bored down the journal centre from its end ----
    # Deliberately DEEP: the retaining screw's head seats on the journal end
    # face, so the bearing play does NOT depend on tap depth (the opposite of
    # the old tap-bottoming scheme). Drilled deeper than tapped for chip
    # relief (left_face_tap_chip_relief).
    tap_drill_r = threads.tap_drill_radius(ds.left_face_tap)
    drill_depth = ds.left_face_tap_depth + ds.left_face_tap_chip_relief
    tap = (
        Pos(-journal_len + drill_depth / 2, 0, 0)
        * Rot(0, 90, 0)
        * Cylinder(radius=tap_drill_r, height=drill_depth)
    )
    body = body - tap  # type: ignore[assignment]

    # --- Lead-in chamfer on the drive-screw +X tip (CNC path only) ---------
    if ds.tip_chamfer > 0 and not params.process.prototype:
        try:
            tip_face = body.faces().sort_by(Axis.X).last
            body = body.chamfer(ds.tip_chamfer, None, list(tip_face.edges()))
        except Exception:
            pass

    # --- Edge chamfer on the knurled disc OD ------------------------------
    # Both circular edges of the disc (where its outer cylinder meets the
    # −X and +X flat faces) — selected by being circular edges at the
    # disc's outer radius.
    if tw.disc_edge_chamfer > 0:
        try:
            disc_edges = [
                e for e in body.edges()
                if e.geom_type == GeomType.CIRCLE and abs(e.radius - disc_r) < 0.05
            ]
            if disc_edges:
                body = body.chamfer(tw.disc_edge_chamfer, None, disc_edges)
        except Exception:
            pass

    return ThumbwheelDriveScrewFeatures(
        boss=boss,
        disc=disc,
        unthreaded=unthreaded,
        thread=thread,
        journal=journal,
        tap=tap,
        body=body,
    )


def build_thumbwheel_drive_screw(params: PurflingCutterParams) -> Part:
    """Build the integral thumbwheel + drive screw."""
    return build_thumbwheel_drive_screw_features(params).body


def main() -> None:
    """CLI: build and export STEP to /tmp/thumbwheel_drive_screw.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    part = build_thumbwheel_drive_screw(params)
    export_step(part, "/tmp/thumbwheel_drive_screw.step")
    print(f"Exported /tmp/thumbwheel_drive_screw.step  (volume = {part.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
