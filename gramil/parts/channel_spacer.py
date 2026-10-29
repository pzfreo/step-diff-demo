"""
Channel spacer — the user-supplied shim between the two blades that sets
the purfling channel width. NOT one of the bone-shaped copper retainers.

Local frame:
  X: thickness (= spacer.thickness, default 1.5 mm) — sets channel width.
  Y: width (matches blade.width).
  Z: length (matches blade.length).

This is a simple flat shim. The user makes / files / buys one of the
right thickness for the channel they want.
"""

from build123d import Box, Part

from gramil.parameters import PurflingCutterParams


def build_channel_spacer(params: PurflingCutterParams) -> Part:
    """Build the channel-width spacer (user-supplied shim)."""
    body: Part = Box(params.spacer.thickness, params.blade.width, params.blade.length)
    return body


def main() -> None:
    from build123d import export_step

    params = PurflingCutterParams()
    spacer = build_channel_spacer(params)
    export_step(spacer, "/tmp/channel_spacer.step")
    print(f"Exported /tmp/channel_spacer.step  (volume = {spacer.volume:.1f} mm^3)")


if __name__ == "__main__":
    main()
