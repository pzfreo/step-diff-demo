"""
Retaining washer for the drive-screw journal bearing — stock M2 flat washer.

The captive screw clamps this washer against the bearing journal's end face;
its outer diameter overhangs the drive plate's bearing hole and retains the
plate on the journal. Its thickness does not affect the bearing play.

Local frame:
  X: washer axis (washer lies in the YZ plane). X = 0 is the centre.
"""

from build123d import Cylinder, Part, Pos, Rot

from gramil.parameters import PurflingCutterParams


def build_washer(params: PurflingCutterParams) -> Part:
    """Build the journal-bearing retaining washer as a build123d Part."""
    w = params.captive_washer
    t = w.thickness
    outer = Pos(0, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=w.outer_diameter / 2, height=t)
    bore = Pos(0, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=w.inner_diameter / 2, height=t + 2)
    body: Part = outer - bore  # type: ignore[assignment]
    return body


def main() -> None:
    """CLI: build the washer and export STEP to /tmp/washer.step."""
    from build123d import export_step

    params = PurflingCutterParams()
    washer = build_washer(params)
    export_step(washer, "/tmp/washer.step")
    print(f"Exported /tmp/washer.step  (volume = {washer.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
