"""
Purfling cutter — parametric model.

Single source of truth for every dimension that crosses a part boundary.
Each numeric field carries spec_ref, status (ESTIMATE | MEASURED | DERIVED),
and units in json_schema_extra.

Wall thicknesses around the four critical bore / slot features (§4.2.13,
§4.2.14, §4.3.23, §4.3.24, §4.3.25) are **derived** from the surrounding
geometry, exposed as computed properties on PurflingCutterParams, and
validated against the spec's minimum-thickness rules. A caller cannot claim a
wall thickness inconsistent with the geometry.

See:
    specification.md   — canonical CAD spec (intent + dimensions)
    code-spec.md       — implementation approach for this build
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from gramil import threads

# ---------------------------------------------------------------------------
# Metadata helper
# ---------------------------------------------------------------------------

Status = Literal["ESTIMATE", "MEASURED", "DERIVED", "DESIGN"]


def _spec(ref: str, status: Status = "ESTIMATE", units: str = "mm") -> dict[str, Any]:
    """Build the json_schema_extra payload tying a field to its spec entry."""
    return {"spec_ref": ref, "status": status, "units": units}


# ---------------------------------------------------------------------------
# Process configuration — prototype vs production fits
# ---------------------------------------------------------------------------


class ProcessConfig(BaseModel):
    """Manufacturing-process flags. Owns the FDM printed-gap clearance.

    The CNC sliding clearance is NOT a parameter here — it falls out of the
    ISO 286 fit classes (bore_fit + shaft_fit on CuttingPairParams). For a
    given nominal diameter the worst-case clearance is computed by
    `gramil.tolerances.worst_case_clearance(...)`.
    """

    model_config = ConfigDict(validate_assignment=True)

    prototype: bool = Field(
        default=True,
        description="True for FDM 3D-print prototype. False for machined brass production.",
    )

    fdm_sliding_clearance: float = Field(
        default=0.25,
        gt=0,
        description="Radial sliding-fit clearance for FDM print. Real printed gap — bore is enlarged by this much over the shaft nominal so the print mates.",
        json_schema_extra=_spec("§8 — Critical fits (prototype override)"),
    )


class CuttingPairParams(BaseModel):
    """The shaft + crossbore mating pair — single nominal diameter with
    ISO 286 fit classes on each side.

    On the CNC path, both shaft and crossbore are nominally the same
    diameter; the bore is reamed at `bore_fit` (typically H7) and the
    shaft is lathed at `shaft_fit` (typically g6), and the clearance
    falls out of the standard tolerance bands.

    On the FDM path, the bore is enlarged by `process.fdm_sliding_clearance`
    to leave room for the printed surfaces; the shaft stays at nominal.
    """

    nominal_diameter: float = Field(
        default=8.0,
        gt=0,
        description="Nominal diameter of the shaft and the crossbore. Picked to match a standard H7 reamer size (8 mm here); the original tool measured 7.9 mm but was rounded up for production simplicity.",
        json_schema_extra=_spec("§4.2.12", status="DERIVED"),
    )
    bore_fit: str = Field(
        default="H7",
        description="ISO 286 fit class for the shank crossbore. H7 = standard reamed-hole sliding fit.",
        json_schema_extra=_spec("§8 — Critical fits", units=""),
    )
    shaft_fit: str = Field(
        default="g6",
        description="ISO 286 fit class for the shaft OD. g6 mates with an H7 hole to give a clearance running fit.",
        json_schema_extra=_spec("§8 — Critical fits", units=""),
    )


# ---------------------------------------------------------------------------
# Tier 1 — Blades and spacer (specification §4.1)
# ---------------------------------------------------------------------------


class BladeParams(BaseModel):
    """§4.1 items 1–4 — blade dimensions."""

    thickness: float = Field(
        default=0.7,
        gt=0,
        description="X dimension when seated in the slot — along the shaft, the direction the grub screw pushes. Across the wide flat of the blade.",
        json_schema_extra=_spec("§4.1.1", status="MEASURED"),
    )
    width: float = Field(
        default=3.6,
        gt=0,
        description="Y dimension when seated — perpendicular to the shaft, fits in the slot's 4.75 mm Y dim with ~0.575 mm clearance per side.",
        json_schema_extra=_spec("§4.1.2", status="MEASURED"),
    )
    length: float = Field(
        default=23.0,
        gt=0,
        description="Z dimension when seated — vertical in use, longer than the slot's Z extent so blades drop through and project below for cutting.",
        json_schema_extra=_spec("§4.1.3", status="MEASURED"),
    )
    bevel_angle: float = Field(
        default=25.0,
        gt=0,
        lt=90,
        description="Single bevel sharpening angle. The manufacturer produces a simple flat-plane bevel wedge at the tip (modelled here as a 25° triangular wedge); the luthier hollow-grinds the visible face and hones the cutting edge to the final shape after delivery.",
        json_schema_extra=_spec("§4.1.4", units="deg"),
    )
    tip_shape: Literal["round", "straight", "angled"] = Field(
        default="round",
        description="Geometry of the blade tip. The original tool's blades have rounded ends.",
        json_schema_extra=_spec("§4.1 (M1.5)", status="MEASURED", units=""),
    )


class SpacerParams(BaseModel):
    """
    §4.1 items 5–6 — channel-width spacer.

    USER-SUPPLIED: the original tool ships with 4 bone-shaped copper
    *retainers* (see BladeRetainerParams) that are NOT the channel-width
    setter. The actual channel width is set by an additional shim that
    the luthier places between the two blades, and is the user's choice
    of thickness. We model it here so the parameter chain still has a
    single source of truth for the channel.
    """

    thickness: float = Field(
        default=0.0,
        ge=0,
        description="X dimension of the user-supplied shim between blades. Sets the purfling channel width. Default 0 = no spacer installed (bare tool state).",
        json_schema_extra=_spec("§4.1.5"),
    )


class BladeRetainerParams(BaseModel):
    """
    Bone-shaped copper retainer.

    *Missing from the original spec.* Four of these per tool, all identical.

    Layout in the slot's X direction (along the shaft, 6.4 mm slot dim): two
    retainers on each side of the blade-spacer-blade stack —
        retainer | retainer | blade | spacer | blade | retainer | retainer
        | grub-screw slack
    Total X stack = 4 × 0.85 + 2 × 0.7 + spacer = 4.8 mm + spacer, leaving
    the remainder of the 6.4 mm slot for grub-screw advance.

    The bone shape locks each retainer in place against the slot's open
    Z direction: the narrow Y middle (4.3 mm) fits inside the slot's
    4.75 mm Y opening, the wider Y ends (5.5 mm) sit above and below the
    slot's +Z and −Z openings so the retainer can't slide through.
    """

    length: float = Field(
        default=10.0,
        gt=0,
        description="Z length of the retainer (long axis = slot's open Z direction). Wider Y ends stick out at the top and bottom of the slot. Measured on the original tool.",
        json_schema_extra=_spec("§4.1 (retainer — missing from spec)", status="MEASURED"),
    )
    middle_length: float = Field(
        default=6.25,
        gt=0,
        description="Z extent of the narrower waist between the two wider end blocks ('shaft of the bone' on the measured tool). The slot's Z extent at the cylinder boundary is 2·√(r²−(W/2)²) = 6.44 mm for r=4, W=4.75 — so the measured 6.25 mm waist leaves the knob inner edges ~0.1 mm inside the cylinder material. The original tool relies on annealed copper compressibility at the four corners to seat without resistance.",
        json_schema_extra=_spec("§4.1 (retainer — missing from spec)", status="MEASURED"),
    )
    end_width: float = Field(
        default=5.5,
        gt=0,
        description="Y width at the bone-shaped ends (at +Z and −Z extremes of the retainer). > slot's 4.75 mm Y so the wider ends sit above and below the slot openings.",
        json_schema_extra=_spec("§4.1 (retainer — missing from spec)", status="MEASURED"),
    )
    middle_width: float = Field(
        default=4.3,
        gt=0,
        description="Y width through the retainer's middle. < slot's 4.75 mm Y so this section fits inside the slot. 4.3 mm gives 0.45 mm nominal waist clearance; the measured original (4.5 mm) is bound to be filed-to-fit, so we machine a hair undersize to leave room for ±0.1 mm copper-cut tolerance.",
        json_schema_extra=_spec("§4.1 (retainer — missing from spec)", status="MEASURED"),
    )
    thickness: float = Field(
        default=0.85,
        gt=0,
        description="X dimension of the flat copper shim — stacks alongside the blades along the shaft.",
        json_schema_extra=_spec("§4.1 (retainer — missing from spec)", status="MEASURED"),
    )
    corner_fillet_radius: float = Field(
        default=1.3,
        ge=0,
        description="Fillet radius on the four outside corners of the bone (the outermost ±Y, ±Z corners of the knob ends). Max usable via the corner-fillet approach is ~1.87 mm (knob Z height − 0.005); OCCT fails at 1.875 mm exactly.",
        json_schema_extra=_spec("§4.1 (retainer — finishing detail)", status="MEASURED"),
    )
    shoulder_fillet_radius: float = Field(
        default=0.5,
        ge=0,
        description="Fillet radius on the four convex 'shoulder' corners where each knob steps inward to the waist (at |Y|=end_width/2, |Z|=middle_length/2). These are the corners that 'stick out' from the waist outline. Max ≤ (end_width − middle_width)/2 = 0.6 mm at defaults. Set 0 to leave them sharp.",
        json_schema_extra=_spec("§4.1 (retainer — finishing detail)", status="DESIGN"),
    )


# ---------------------------------------------------------------------------
# Tier 2 — Shaft (specification §4.2)
# ---------------------------------------------------------------------------


class GrubScrewParams(BaseModel):
    """§4.2 items 15–16 — blade-clamp grub screw."""

    thread: str = Field(
        default="M4",
        description="Grub-screw thread. Original tool has a non-standard 4.4 mm diameter — we substitute M4 (4 mm) as the closest convenient standard size.",
        json_schema_extra=_spec("§4.2.15", status="MEASURED", units=""),
    )
    length: float = Field(
        default=5.0,
        gt=0,
        description="Total threaded length of the grub screw. M4 × 5 mm — fully inserted, sitting flush (not proud) of the shaft's +X end face when its nose clamps the stack. (The earlier M4 × 10 was a placeholder that stuck ~4.4 mm out past the end face.)",
        json_schema_extra=_spec("§4.2 (grub screw length — not numbered)", status="MEASURED"),
    )
    max_nose_advance: float = Field(
        default=3.0,
        gt=0,
        description="Max distance the nose extends past the right wall of the blade slot.",
        json_schema_extra=_spec("§4.2.16"),
    )


class ShaftParams(BaseModel):
    """§4.2 items 8–19 — shaft dimensions."""

    cross_section: Literal["round", "round_with_flat"] = Field(
        default="round_with_flat",
        description="Shaft cross-section profile. Measured: the original has a flat machined on the underside that registers against the depth-lock push rod — answers spec §5 open question Q3. Flat-on-flat contact gives a more positive lock AND prevents shaft rotation.",
        json_schema_extra=_spec("§4.2.11", status="MEASURED", units=""),
    )
    flat_depth: float = Field(
        default=0.6,
        gt=0,
        description="Depth of the flat machined on the −Z underside of the shaft — the sagitta of the cylinder segment removed from the bottom. Flat extends the full shaft.length.",
        json_schema_extra=_spec("§4.2.11 (flat — not in spec items)", status="MEASURED"),
    )
    drive_plate_mount_depth: float = Field(
        default=5.0,
        gt=0,
        description="Depth of the tapped holes on the shaft's outboard end face (for the drive-plate screws). ESTIMATE.",
        json_schema_extra=_spec("§4.2.19 (mount depth — not numbered)"),
    )
    # Note: shaft OD is no longer a field on ShaftParams — it now derives
    # from PurflingCutterParams.cutting_pair.nominal_diameter. The shaft's
    # OD is one half of a mating pair and must stay in lockstep with the
    # crossbore. Access via params.shaft_outer_diameter at the top level.

    blade_slot_width: float = Field(
        default=6.4,
        gt=0,
        description="X dimension of blade slot (along the shaft). Hardware stack (4 retainers × 0.85 + 2 blades × 0.7) = 4.8 mm; remaining ~1.6 mm is shared between the channel spacer and grub-screw advance.",
        json_schema_extra=_spec("§4.2.8", status="MEASURED"),
    )
    blade_slot_length: float = Field(
        default=4.75,
        gt=0,
        description="Y dimension of blade slot (across the shaft). Fits blade.width (3.6 mm) plus ~0.575 mm clearance per side. Z is the open through direction (blades drop through).",
        json_schema_extra=_spec("§4.2.9", status="MEASURED"),
    )
    end_to_slot_distance: float = Field(
        default=4.0,
        gt=0,
        description="Distance from shaft right end face to right wall of blade slot. The grub-screw end tap fills this entire distance — there is *no* wall between the tap and the slot, so the grub screw's tip directly contacts the blade stack. (Spec §4.2.14 wall rule does not apply to this tool's design.)",
        json_schema_extra=_spec("§4.2.17", status="MEASURED"),
    )
    length: float = Field(
        default=37.6,
        gt=0,
        description="Total shaft length. Extended from the measured 35 mm to 37.6 mm so the blade slot moves outboard far enough that the engaged drive-screw thread tip clears the slot's inboard (near) wall by 1.5 mm — otherwise a bone-less blade dropped into the slot fouls the screw (see PurflingCutterParams.drive_screw_tip_to_slot_clearance). Moving the slot outboard also raises the max edge-margin, which is what's needed for double purfling.",
        json_schema_extra=_spec("§4.2.18", status="DESIGN"),
    )
    end_chamfer: float = Field(
        default=1.5,
        ge=0,
        description="45° chamfer on the OUTER (OD) corner of the +X end face — the grub-screw / blade end. Breaks the sharp rim so it's a clean lead-in and comfortable to handle. Capped by the M4 grub TAP: the chamfer inner edge is at r = 4 − chamfer, and must stay outside the M4 thread crest (Ø4, r=2) or it eats the thread mouth. 1.5 mm → inner Ø5, a 0.5 mm land to the thread (2 mm would land exactly on the Ø4 crest — no seat). Applied to the full-circle end before the flat/bore cuts so it builds cleanly. 0 disables.",
        json_schema_extra=_spec("§4.2 (end chamfer — design addition)", status="DESIGN"),
    )
    drive_plate_mount_thread: str = Field(
        default="M2",
        description="Thread for the single central screw mounting the drive plate to the shaft's outboard end face. Spec called for two screws; this scale (~7.9 mm shaft) doesn't fit two M2 screws, so we go with one + use the shaft's existing −Z flat as the anti-rotation feature (the drive plate has a matching D-shaped hole that mates with the shaft cross-section).",
        json_schema_extra=_spec("§4.2.19", units=""),
    )


# ---------------------------------------------------------------------------
# Tier 3 — Shank (specification §4.3)
# ---------------------------------------------------------------------------


class DepthLockParams(BaseModel):
    """
    §4.3 item 32 — depth-lock bolt, thumbwheel, and push rod.

    Mechanism (corrected from spec): the bolt's tip does NOT bear on the shaft
    directly. Instead, the depth-lock bore is tapped for only the lower portion;
    above the threaded section sits a free-sliding steel push rod. Tightening
    the thumbwheel advances the bolt, which pushes the rod up against the
    underside of the shaft. The spec's `Depth-lock bolt — its upper end bears
    directly on the underside of the shaft` is incorrect; the push rod is the
    intermediary.
    """

    thread: str = Field(
        default="M6",
        description="Depth-lock bolt thread (measured OD = 6 mm → M6).",
        json_schema_extra=_spec("§4.3.32", status="MEASURED", units=""),
    )
    bolt_thread_length: float = Field(
        default=13.0,
        gt=0,
        description="Length of the threaded portion of the depth-lock bolt (above the collar). 13 mm — gives 1 mm of preload margin between the rod-lock contact and the knob bottoming on the shank (see locking calc).",
        json_schema_extra=_spec("§4.3 (bolt — not numbered)", status="MEASURED"),
    )
    bolt_collar_diameter: float = Field(
        default=6.25,
        gt=0,
        description="Outside diameter of the unthreaded collar between the knob and the threaded shaft. Slightly larger than the M6 thread major; mates with the enlarged section of the shank's depth-lock bore as an anti-cocking guide.",
        json_schema_extra=_spec("§4.3 (collar — design addition)", status="MEASURED"),
    )
    bolt_collar_length: float = Field(
        default=5.0,
        gt=0,
        description="Z length of the unthreaded collar between knob and thread.",
        json_schema_extra=_spec("§4.3 (collar — design addition)", status="MEASURED"),
    )
    bolt_tip_chamfer: float = Field(
        default=1.0,
        ge=0,
        description="Lead-in chamfer height on the bolt's thread tip. 1 mm = one full thread pitch for M6 × 1; visible lead-in that helps the bolt start threading without cross-threading.",
        json_schema_extra=_spec("§4.3 (chamfer — design addition)", status="MEASURED"),
    )
    knob_diameter: float = Field(
        default=10.0,
        gt=0,
        description="Thumbwheel OD at the bottom of the shank.",
        json_schema_extra=_spec("§4.3 (knob — not numbered)", status="MEASURED"),
    )
    knob_thickness: float = Field(
        default=14.0,
        gt=0,
        description="Thumbwheel length along the bolt axis (Z).",
        json_schema_extra=_spec("§4.3 (knob — not numbered)", status="MEASURED"),
    )
    knob_bottom_chamfer: float = Field(
        default=1.5,
        ge=0,
        description="Large chamfer on the bottom (−Z) edge of the knurled knob. The bottom is the hand-facing end; the chamfer bevels the otherwise-sharp circumference so the knob is comfortable to grip and visually finished.",
        json_schema_extra=_spec("§4.3 (chamfer — design addition)", status="MEASURED"),
    )
    knurl_pitch: float = Field(
        default=0.8,
        gt=0,
        description="Knurl pitch (tooth spacing) on the knob, as a drawing callout (the knurl decoration itself is not modelled). 0.8 mm matches the thumbwheel: blunter, more durable, grippier teeth than the original fine 0.5 mm knurl.",
        json_schema_extra=_spec("§4.3 (knurl pitch — design addition)", status="DESIGN"),
    )
    push_rod_diameter: float = Field(
        default=4.5,
        gt=0,
        description="Steel push-rod diameter. ⌀4.5 in a ⌀5 bore (M6 tap drill = 5.0, so the smooth section above the tap is also 5.0) gives 0.25 mm radial clearance — comfortable sliding fit.",
        json_schema_extra=_spec("§4.3 (push rod — missing from spec)", status="MEASURED"),
    )
    lock_preload_margin: float = Field(
        default=2.0,
        gt=0,
        description="Clamp-travel headroom for the depth lock: how far the bolt can still advance after the push rod first contacts the shaft's −Z flat, before the knob bottoms on the shank's bottom face. This remaining travel is what gets converted into clamping preload, and it's how far the bolt sits proud at lock. Set to 2.0 mm → derived rod 46.6 mm. The rod is cut to length with NO machining tolerance (≈±1 mm in practice), and too-SHORT is the dangerous direction — below ~44.6 mm the rod can't reach the flat to clamp at all, and ~45 mm barely clamps — whereas too-long merely leaves the bolt slightly proud. So we err long: a 2.0 mm nominal margin keeps even a −1 mm cut (45.6 mm) at the empirically-good 1.0 mm clamp, while a +1 mm cut (47.6 mm) only sits a little proud. MEASURED: a 44.3 mm as-cut rod needed a 1.3 mm shim → 45.6 mm = 1.0 mm clamp works. (An earlier 3.0 mm value put the nominal at 47.6 mm — too long.)",
        json_schema_extra=_spec("§4.3 (push rod — missing from spec)", status="DESIGN"),
    )


class ShankParams(BaseModel):
    """§4.3 items 20–36 — shank dimensions (user-set; walls are derived on the top-level model)."""

    width: float = Field(
        default=13.55,
        gt=0,
        description="Shank cross-section X dimension (from back of shank to peak of convex working face, includes sagitta).",
        json_schema_extra=_spec("§4.3.26", status="MEASURED"),
    )
    depth: float = Field(
        default=11.0,
        gt=0,
        description="Shank cross-section Y dimension (across the working face).",
        json_schema_extra=_spec("§4.3.26", status="MEASURED"),
    )
    length: float = Field(
        default=80.0,
        gt=0,
        description="Shank length along Z. Affects balance, reach, depth-lock bore length.",
        json_schema_extra=_spec("§4.3.27", status="MEASURED"),
    )
    crossbore_position_from_top: float = Field(
        default=14.0,
        gt=0,
        description="Distance from the top of the shank to the shaft cross-bore axis.",
        json_schema_extra=_spec("§4.3.28", status="MEASURED"),
    )
    crossbore_to_tapped_bore_gap: float = Field(
        default=9.5,
        gt=0,
        description="Centre-to-centre distance between shaft cross-bore and shank tapped bore. Derived from measured crossbore_position_from_top (14) − tapped-bore-position-from-top (4.5).",
        json_schema_extra=_spec("§4.3.22", status="DERIVED"),
    )
    depth_lock_bore_diameter: float = Field(
        default=5.0,
        gt=0,
        description="Depth-lock blind bore diameter. M6 tap drill is 5.0 mm; same diameter also accepts the 5 mm push rod (sliding fit in the untapped upper section).",
        json_schema_extra=_spec("§4.3.30", status="DERIVED"),
    )
    depth_lock_collar_bore_diameter: float = Field(
        default=6.35,
        gt=0,
        description="Diameter of the enlarged section at the BOTTOM of the depth-lock bore. Receives the bolt's 6.25 collar with light sliding clearance (~0.05 mm radial), giving an anti-cocking guide that locates the bolt in the working clamping range.",
        json_schema_extra=_spec("§4.3 (collar bore — design addition)", status="MEASURED"),
    )
    depth_lock_collar_bore_length: float = Field(
        default=5.5,
        gt=0,
        description="Length of the enlarged collar-bore section. 0.5 mm longer than the bolt's collar so manufacturing tolerance on either feature can't cause the collar to bottom against the tap shoulder.",
        json_schema_extra=_spec("§4.3 (collar bore — design addition)", status="MEASURED"),
    )
    depth_lock_threaded_length: float = Field(
        default=12.0,
        gt=0,
        description="Length of the M6-tapped section immediately ABOVE the collar bore. The remainder of the bore (up to the crossbore) is a smooth sliding fit for the push rod.",
        json_schema_extra=_spec("§4.3 (threading depth — not in spec)"),
    )
    relief_slot_width: float = Field(
        default=2.0,
        gt=0,
        description="Relief slot Y width — central groove down the working face.",
        json_schema_extra=_spec("§4.3.33", status="MEASURED"),
    )
    relief_slot_depth: float = Field(
        default=1.0,
        gt=0,
        description="Relief slot X depth — into body from working face. 1 mm at deepest (centre); slightly less at slot edges where the convex face is lower.",
        json_schema_extra=_spec("§4.3.34", status="MEASURED"),
    )
    working_face_radius: float = Field(
        default=8.11,
        gt=0,
        description="Convexity radius of working face. Derived from measured sagitta 2.15 mm over chord depth 11 mm: R = (c² + 4s²)/(8s).",
        json_schema_extra=_spec("§4.3.35", status="DERIVED"),
    )
    top_dome_radius: float = Field(
        default=30.0,
        gt=0,
        description="Radius of the spherical dome at the +Z end of the shank. Rounded in *both* X and Y directions (sphere, not a single-axis cylinder). Must be large enough that the dome's lowest point (at the +X +Y corner) sits above the top of the tapped bore — empirically requires R ≥ ~15 mm for the current shank/bore proportions. R = 30 mm gives a ~1.5 mm wall above the bore.",
        json_schema_extra=_spec("§4.3 (top dome — not in spec)"),
    )
    edge_fillet_radius: float = Field(
        default=1.0,
        ge=0,
        description="Radius of fillet applied to every external edge of the shank.",
        json_schema_extra=_spec("§8 (finishing — not in §4)", status="MEASURED"),
    )


# ---------------------------------------------------------------------------
# Tier 4 — Drive train (specification §4.4)
# ---------------------------------------------------------------------------


class DriveScrewParams(BaseModel):
    """§4.4 items 37–40, 44 — drive screw (integral with thumbwheel)."""

    thread: str = Field(
        default="M3",
        description="Drive-screw thread (measured OD = 3 mm → M3). Matches shank tapped bore (§4.3.21), which is fully threaded along its full X length (= shank.width).",
        json_schema_extra=_spec("§4.4.37", status="MEASURED", units=""),
    )
    thread_pitch: float = Field(
        default=0.5,
        gt=0,
        description="Drive-screw thread pitch = 0.5 mm — the STANDARD COARSE pitch for M3 (M3 'fine' would be 0.35). The drive screw and shank tapped bore are therefore cut and gauged with standard M3 taps and dies (~2 turns/mm of edge-margin feed). NOTE: earlier mislabelled 'fine pitch', which risks a 0.35 part that won't mate with a 0.5 one.",
        json_schema_extra=_spec("§4.4.38", status="MEASURED"),
    )
    length: float = Field(
        default=20.0,
        gt=0,
        description="Threaded length of the M3 drive screw. 20 mm matches the as-supplied part (total thumbwheel+screw = boss 0.5 + disc 2 + unthreaded 3 + thread 20 = 25.5 mm). NOTE: the thread length does NOT set the maximum edge-margin — that is limited by the unthreaded shoulder seating on the shank's back face. The long thread governs the minimum-margin (retracted) travel, and its tip must clear the blade slot (see shaft.length and drive_screw_tip_to_slot_clearance).",
        json_schema_extra=_spec("§4.4.39", status="MEASURED"),
    )
    tip_chamfer: float = Field(
        default=0.5,
        ge=0,
        description="Lead-in chamfer height on the drive screw's +X thread tip. Helps the drive screw enter and start threading in the shank tapped bore.",
        json_schema_extra=_spec("§4.4 (chamfer — design addition)", status="MEASURED"),
    )
    left_face_tap: str = Field(
        default="M2",
        description="Thread of the tap on the thumbwheel's left end face (for captive screw).",
        json_schema_extra=_spec("§4.4.40", status="MEASURED", units=""),
    )
    left_face_tap_depth: float = Field(
        default=7.0,
        gt=0,
        description="Depth of the M2 tap bored down the centre of the bearing journal (from the journal end face inward). In the integral-journal bearing the retaining screw's HEAD seats on the journal end face (the play is set by journal_length − plate.thickness, not by the screw bottoming), so the tap is deliberately DEEP — ≥ the captive-screw thread length — so the head always seats before the screw bottoms. Tapping deeper is harmless here (the opposite of the old tap-bottoming scheme, which a too-deep tap broke).",
        json_schema_extra=_spec("§4.4.40", status="DESIGN"),
    )
    left_face_tap_chip_relief: float = Field(
        default=1.0,
        ge=0,
        description="Extra depth drilled past the bottom of the M2 tap as a chip-relief well. Avoids the bottoming-tap requirement: shop drills tap_depth + chip_relief, taps with a standard plug tap to tap_depth, chips clear into the relief. The screw still bottoms on the tapped section at the same Z, so captive-bearing geometry is unchanged.",
        json_schema_extra=_spec("§4.4 (chip relief — manufacturing aid)", status="MEASURED"),
    )
    unthreaded_length: float = Field(
        default=3.0,
        gt=0,
        description="Length of the unthreaded section between the thumbwheel disc and the start of the M3 threaded portion of the drive screw. Provides solid material around the captive-screw tap bottom so it doesn't eat into the M3 thread.",
        json_schema_extra=_spec("§4.4 (unthreaded section — design addition)", status="MEASURED"),
    )
    unthreaded_diameter: float = Field(
        default=5.0,
        gt=0,
        description="Outer diameter of the unthreaded section. Larger than M3 major (3 mm) so it provides a positive shoulder against the inboard face of the shank tapped bore at maximum-margin.",
        json_schema_extra=_spec("§4.4 (unthreaded section — design addition)", status="MEASURED"),
    )
    bearing_journal_diameter: float = Field(
        default=4.0,
        gt=0,
        description="Diameter of the integral bearing journal turned on the thumbwheel boss (−X) face. The drive plate's thumb-end hole rides on this journal. ⌀4.0 leaves a 1.0 mm wall around the M2 retaining tap ((4 − M2 major 2)/2), matching the tool's ≥1 mm tapped-bore wall rule. Must be < boss_diameter so the boss face forms a thrust shoulder for the plate.",
        json_schema_extra=_spec("§4.4 (journal bearing — design addition)", status="DESIGN"),
    )
    bearing_journal_clearance: float = Field(
        default=0.2,
        gt=0,
        description="Diametral running clearance between the bearing journal and the drive plate's bearing hole (plate hole = journal diameter + this). A loose journal-bearing fit so the plate floats and the drive screw turns freely.",
        json_schema_extra=_spec("§4.4 (journal bearing — design addition)", status="DESIGN"),
    )


class ThumbwheelParams(BaseModel):
    """§4.4 items 41–43 — thumbwheel (integral with drive screw)."""

    diameter: float = Field(
        default=10.0,
        gt=0,
        description="Thumbwheel knurled disc OD. Original measured at 9.5 mm; rounded to 10 mm for the prototype (interchangeable with 9 mm by user choice).",
        json_schema_extra=_spec("§4.4.41", status="MEASURED"),
    )
    thickness: float = Field(
        default=2.0,
        gt=0,
        description="Thumbwheel thickness (X dimension — along the drive-screw axis).",
        json_schema_extra=_spec("§4.4.42", status="MEASURED"),
    )
    boss_diameter: float = Field(
        default=6.0,
        gt=0,
        description="Diameter of the small boss on the outboard (−X, drive-plate side) face of the thumbwheel. The captive-screw tap enters through this boss, giving extra material around the tap so it doesn't eat into the thumbwheel's knurled edge.",
        json_schema_extra=_spec("§4.4 (boss — design addition)", status="MEASURED"),
    )
    boss_length: float = Field(
        default=0.5,
        gt=0,
        description="X length of the boss. Short — just enough to give a positive seat for the captive-screw tap.",
        json_schema_extra=_spec("§4.4 (boss — design addition)", status="MEASURED"),
    )
    knurl: Literal["straight", "diamond"] = Field(
        default="straight",
        description="Knurl pattern style.",
        json_schema_extra=_spec("§4.4.43", units=""),
    )
    knurl_pitch: float = Field(
        default=0.8,
        gt=0,
        description="Knurl pitch (tooth spacing). Coarsened from the original 0.5 mm: on the brass wheel a 0.5 mm knurl gives small, sharp teeth that are fragile and not very grippy — 0.8 mm gives blunter, more durable teeth that also grip better.",
        json_schema_extra=_spec("§4.4.43 (pitch — design addition)", status="DESIGN"),
    )
    disc_edge_chamfer: float = Field(
        default=0.3,
        ge=0,
        description="Small chamfer on the two circular edges of the knurled disc (where the OD meets the −X and +X flat faces). Breaks the sharp edges so the user doesn't catch a fingertip when spinning the wheel.",
        json_schema_extra=_spec("§4.4 (chamfer — design addition)", status="MEASURED"),
    )


# ---------------------------------------------------------------------------
# Tier 5 — Drive plate and captive bearing (specification §4.5)
# ---------------------------------------------------------------------------


class DrivePlateParams(BaseModel):
    """
    §4.5 items 45–49 — drive plate that lets the drive screw pull the shaft.

    The real plate is **egg-shaped** (NOT the rectangle the spec drafted):
    two circular bosses, the larger one at the shaft end (10 mm radius)
    and the smaller one at the thumbwheel end (5 mm radius), connected
    by a smooth tangent boundary. The plate's plane is YZ (normal = X),
    standing vertically up from the shaft's outboard −X end face.

    The vertical distance between the two bosses' centres equals the
    shank's `crossbore_to_tapped_bore_gap` so the plate spans from the
    shaft axis up to the drive-screw axis.
    """

    shaft_end_radius: float = Field(
        default=4.0,
        gt=0,
        description="Radius of the larger boss at the shaft end of the plate (8 mm diameter) — matched to the shaft OD so the plate's bottom edge is flush with the shaft and the 8 mm tenon goes edge-to-edge with no overhang.",
        json_schema_extra=_spec("§4.5.45 (egg shape — not in spec)", status="MEASURED"),
    )
    thumb_end_radius: float = Field(
        default=3.0,
        gt=0,
        description="Radius of the smaller boss at the thumbwheel end (6 mm diameter), around the captive-screw clearance hole.",
        json_schema_extra=_spec("§4.5.45 (egg shape — not in spec)", status="MEASURED"),
    )
    thickness: float = Field(
        default=3.0,
        gt=0,
        description="Plate thickness (X dimension — the plate's normal direction). 3 mm = 1 mm anti-rotation slot + 2 mm wall on the front face.",
        json_schema_extra=_spec("§4.5.47", status="MEASURED"),
    )
    captive_clearance_hole_diameter: float = Field(
        default=2.6,
        gt=0,
        description="Hole the CAPTIVE screw passes through. Deliberately sloppy (~0.3 mm radial clearance on M2) — the plate rides on the captive screw as a bearing, so it needs more clearance than a standard screw hole.",
        json_schema_extra=_spec("§4.5.48"),
    )
    mount_hole_diameter: float = Field(
        default=2.4,
        gt=0,
        description="Hole the MOUNT screw passes through (shaft end of plate). Standard M2 clearance fit (~0.2 mm radial). Doesn't need the sloppy captive-bearing tolerance.",
        json_schema_extra=_spec("§4.5 (mount hole — distinct from captive-screw hole)"),
    )
    tenon_depth: float = Field(
        default=1.5,
        gt=0,
        description="X projection of the anti-rotation tenon outboard from the plate's +X (back) face into the matching slot in the shaft's −X end face. The tenon is on the plate (not the shaft) so the plate keeps its full 3 mm thickness in the load-bearing region.",
        json_schema_extra=_spec("§4.5 (tenon — design addition)", status="MEASURED"),
    )
    tenon_height: float = Field(
        default=3.0,
        gt=0,
        description="Z dimension of the anti-rotation tenon — a horizontal rib at Z = 0 (shaft-end boss centre) on the plate's back face.",
        json_schema_extra=_spec("§4.5 (tenon — design addition)", status="MEASURED"),
    )
    # Note: tenon Y extent is derived from the plate's outline at the tenon's
    # Z range (the tenon is built as a clipped extrusion of the egg shape),
    # so there is no separate tenon_width parameter. The tenon edges follow
    # the plate's perimeter exactly — no protruding corners.


class CaptiveScrewParams(BaseModel):
    """§4.5 items 50, 52 — captive (retaining) screw for the journal bearing.

    A stock M2 pan-head. In the integral-journal bearing it threads into the
    deep tap down the journal centre and clamps the retaining washer against
    the journal end face (metal-to-metal). The play is set by the journal
    length, NOT by how this screw bottoms, so it can be torqued fully.
    """

    thread: str = Field(
        default="M2",
        description="Captive-screw thread. Matches drive_screw.left_face_tap (§4.4.40).",
        json_schema_extra=_spec("§4.5.50", status="MEASURED", units=""),
    )
    thread_length: float = Field(
        default=6.0,
        gt=0,
        description="Length of the threaded portion (head excluded), in mm. Default 6 mm = stock M2 × 6 brass screw. The journal tap (drive_screw.left_face_tap_depth) is cut deeper than this so the head seats positively on the journal end face before the screw bottoms.",
        json_schema_extra=_spec("§4.5.51", status="MEASURED"),
    )
    head_diameter: float = Field(
        default=4.0,
        gt=0,
        description="Head diameter (measured). Clamps the retaining washer; the washer (not the head) is what overhangs and retains the plate's bearing hole.",
        json_schema_extra=_spec("§4.5.52", status="MEASURED"),
    )
    head_thickness: float = Field(
        default=1.5,
        gt=0,
        description="Head thickness.",
        json_schema_extra=_spec("§4.5.52"),
    )


class MountScrewParams(BaseModel):
    """The drive-plate mount screw — any stock M2 pan-head will do.

    Passes through the drive plate's central clearance hole, through the
    tenon (which sits in the shaft's end slot), and into the M2 tap on
    the shaft's −X end face.
    """

    thread: str = Field(
        default="M2",
        description="Mount-screw thread. Matches shaft.drive_plate_mount_thread.",
        json_schema_extra=_spec("§4.2.19 (mount screw)", status="MEASURED", units=""),
    )
    thread_length: float = Field(
        default=10.0,
        gt=0,
        description="Stock M2 × 10 mm screw. Passes through plate (3) + tenon (1.5) and engages the shaft tap (5 mm) with a bit of margin.",
        json_schema_extra=_spec("§4.2.19 (mount screw)", status="MEASURED"),
    )
    head_diameter: float = Field(
        default=4.0,
        gt=0,
        description="Head diameter (measured). Must exceed drive_plate.mount_hole_diameter.",
        json_schema_extra=_spec("§4.2.19 (mount screw)", status="MEASURED"),
    )
    head_thickness: float = Field(
        default=1.5,
        gt=0,
        description="Head thickness.",
        json_schema_extra=_spec("§4.2.19 (mount screw)"),
    )


class CaptiveBearingParams(BaseModel):
    """
    §4.5 item 53 — the signature mechanism of this tool: an integral
    journal bearing.

    A journal (drive_screw.bearing_journal_diameter) is turned on the
    thumbwheel boss face. The drive plate's thumb-end hole rides on it. A
    retaining washer + M2 screw caps the journal end, capturing the plate
    on the journal with a small axial float. The axial play is set purely
    by two precise turned/milled lengths:

        axial_play = bearing_journal_length − drive_plate.thickness
                   = (drive_plate.thickness + axial_play) − drive_plate.thickness

    i.e. the journal is machined `axial_play` longer than the plate is thick.
    This replaces the older "captive screw bottoms in a shallow tap" scheme,
    whose play was the fragile leftover of three stacked dimensions and which
    a too-deep tap destroyed. Tap depth no longer affects the play.
    """

    axial_play: float = Field(
        default=0.2,
        gt=0,
        le=0.5,
        description="Designed axial bearing float — the non-binding gap that lets the drive plate slide on the journal while the drive screw rotates freely. Realised as bearing_journal_length − drive_plate.thickness, so it's set by two CNC length dims (robust to ±0.05 mm general tolerance) rather than a screw bottoming in a tap.",
        json_schema_extra=_spec("§4.5.53", status="DESIGN"),
    )


class WasherParams(BaseModel):
    """Retaining washer for the journal bearing — stock M2 flat washer.

    Clamped by the captive screw against the bearing journal's end face; its
    outer diameter overhangs the plate's bearing hole to retain the plate on
    the journal. Its thickness does NOT affect the axial play (the play is the
    journal-length-minus-plate-thickness float on the journal, inboard of the
    washer).
    """

    outer_diameter: float = Field(
        default=5.0,
        gt=0,
        description="Washer OD (stock M2 flat washer). Must exceed the plate bearing hole so it retains the plate.",
        json_schema_extra=_spec("§4.5 (retaining washer — design addition)", status="MEASURED"),
    )
    inner_diameter: float = Field(
        default=2.2,
        gt=0,
        description="Washer bore — M2 clearance.",
        json_schema_extra=_spec("§4.5 (retaining washer — design addition)", status="MEASURED"),
    )
    thickness: float = Field(
        default=0.3,
        gt=0,
        description="Washer thickness (stock M2). Does not affect the bearing play.",
        json_schema_extra=_spec("§4.5 (retaining washer — design addition)", status="MEASURED"),
    )


# ---------------------------------------------------------------------------
# Top-level model — composes sub-models, owns cross-part derivations
# ---------------------------------------------------------------------------


class PurflingCutterParams(BaseModel):
    """
    Top-level parameter set for the purfling cutter.

    Cross-part derived values (stack thickness, bore diameter, wall thicknesses)
    are exposed as computed properties. Wall-thickness rules from §4 of
    specification.md are enforced as a model validator: invalid geometry raises
    ValidationError.
    """

    process: ProcessConfig = Field(default_factory=ProcessConfig)
    cutting_pair: CuttingPairParams = Field(default_factory=CuttingPairParams)
    blade: BladeParams = Field(default_factory=BladeParams)
    spacer: SpacerParams = Field(default_factory=SpacerParams)
    blade_retainer: BladeRetainerParams = Field(default_factory=BladeRetainerParams)
    grub_screw: GrubScrewParams = Field(default_factory=GrubScrewParams)
    shaft: ShaftParams = Field(default_factory=ShaftParams)
    shank: ShankParams = Field(default_factory=ShankParams)
    depth_lock: DepthLockParams = Field(default_factory=DepthLockParams)
    drive_screw: DriveScrewParams = Field(default_factory=DriveScrewParams)
    thumbwheel: ThumbwheelParams = Field(default_factory=ThumbwheelParams)
    drive_plate: DrivePlateParams = Field(default_factory=DrivePlateParams)
    captive_screw: CaptiveScrewParams = Field(default_factory=CaptiveScrewParams)
    mount_screw: MountScrewParams = Field(default_factory=MountScrewParams)
    captive_bearing: CaptiveBearingParams = Field(default_factory=CaptiveBearingParams)
    captive_washer: WasherParams = Field(default_factory=WasherParams)

    # --- Mating-pair derivations (cutting_pair + process) ------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def shaft_outer_diameter(self) -> float:
        """Nominal shaft OD — the cutting-pair nominal. Tolerance class
        (e.g. g6) lives on cutting_pair.shaft_fit and is rendered on the
        drawing, not numerically expanded here."""
        return self.cutting_pair.nominal_diameter

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sliding_clearance(self) -> float:
        """Active sliding-fit clearance for the current process.

        FDM: a real printed gap (process.fdm_sliding_clearance).
        CNC: the ISO 286 worst-case clearance for the bore/shaft fit pair.
        """
        if self.process.prototype:
            return self.process.fdm_sliding_clearance
        from gramil import tolerances

        return tolerances.worst_case_clearance(
            self.cutting_pair.nominal_diameter,
            hole_fit=self.cutting_pair.bore_fit,
            shaft_fit=self.cutting_pair.shaft_fit,
        )

    # --- Cross-part derived values (§4 derivations) -------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stack_thickness(self) -> float:
        """
        §4.1.7 — permanent hardware stack in X direction (along shaft).

        Layout: retainer | retainer | blade | blade | retainer | retainer.
        The channel spacer sits in the remaining spare space between the two
        blades; it is NOT part of this fixed stack. Spare space for spacer +
        grub-screw advance = blade_slot_width − stack_thickness (~1.6 mm with
        defaults).
        """
        return 4 * self.blade_retainer.thickness + 2 * self.blade.thickness

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slot_spare(self) -> float:
        """X space available for channel spacer + grub-screw advance (hardware stack only)."""
        return self.shaft.blade_slot_width - self.stack_thickness

    @computed_field  # type: ignore[prop-decorator]
    @property
    def drive_screw_total_length(self) -> float:
        """Total length of the integral thumbwheel + drive-screw piece along X,
        from the boss (−X) face to the thread tip (+X)."""
        return (
            self.thumbwheel.boss_length
            + self.thumbwheel.thickness
            + self.drive_screw.unthreaded_length
            + self.drive_screw.length
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bearing_journal_length(self) -> float:
        """Length of the integral bearing journal along X. Machined `axial_play`
        longer than the plate is thick, so the plate floats by exactly the
        axial play on the journal between the boss-face shoulder and the
        journal-end washer."""
        return self.drive_plate.thickness + self.captive_bearing.axial_play

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plate_bearing_hole_diameter(self) -> float:
        """Diameter of the drive plate's thumb-end hole that rides on the
        journal = journal diameter + diametral running clearance."""
        return (
            self.drive_screw.bearing_journal_diameter
            + self.drive_screw.bearing_journal_clearance
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def drive_screw_tip_to_slot_clearance(self) -> float:
        """
        Axial (X) clearance between the drive-screw thread tip and the inboard
        (near) wall of the blade slot.

        The drive screw, drive plate, shaft and blades are all coupled and
        translate together, so this clearance is FIXED — it does not change
        with the edge-margin setting. Measuring from the shaft's −X (drive)
        end (the journal bearing puts the thumbwheel boss face flush at the
        plate / shaft end, so the screw stack starts there):

            shaft end → slot near wall = shaft.length − end_to_slot − blade_slot_width
            shaft end → screw tip      = drive_screw_total_length

        It must stay positive (with margin), or the engaged drive-screw tip
        fouls a bone-less blade dropped into the slot.
        """
        slot_near = (
            self.shaft.length
            - self.shaft.end_to_slot_distance
            - self.shaft.blade_slot_width
        )
        return slot_near - self.drive_screw_total_length

    @computed_field  # type: ignore[prop-decorator]
    @property
    def crossbore_diameter(self) -> float:
        """§4.3.20 — modelled crossbore diameter for boolean geometry.

        FDM: shaft nominal + printed gap (the geometry literally needs the
        bore enlarged so the printed shaft will fit).
        CNC: the same nominal as the shaft — the fit class on the drawing
        (e.g. H7) carries the tolerance, not the modelled geometry.
        """
        if self.process.prototype:
            return self.cutting_pair.nominal_diameter + self.process.fdm_sliding_clearance
        return self.cutting_pair.nominal_diameter

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tapped_bore_drill_diameter(self) -> float:
        """Drill diameter for the shank tapped bore — derived from drive-screw thread."""
        return threads.tap_drill_diameter(self.drive_screw.thread)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tapped_bore_position_from_top(self) -> float:
        """§4.3.29 — tapped bore sits above the crossbore, so closer to the top."""
        return self.shank.crossbore_position_from_top - self.shank.crossbore_to_tapped_bore_gap

    @computed_field  # type: ignore[prop-decorator]
    @property
    def depth_lock_bore_depth(self) -> float:
        """
        §4.3.31 — bore extends from the bottom face up to the crossbore axis.

        Originally the spec called for a `small_clearance` so the bore stopped
        just below the crossbore. Measurement showed the bore actually meets
        the crossbore (it has to — the push rod's upper end sits in the
        crossbore region so it can press on the shaft). So no clearance term.
        """
        return self.shank.length - self.shank.crossbore_position_from_top

    @computed_field  # type: ignore[prop-decorator]
    @property
    def push_rod_length(self) -> float:
        """
        Depth-lock push-rod length — DERIVED, not measured.

        The rod spans from the depth-lock bolt's tip up to the shaft's −Z
        flat. Geometry in the shank frame (Z = 0 at the shank bottom face):

          rod top (contact on the shaft flat):
              shaft_flat_z = depth_lock_bore_depth
                             − shaft_outer_diameter/2 + shaft.flat_depth
          bolt tip at full advance (knob bottomed on the shank bottom face):
              bolt_tip = bolt_collar_length + bolt_thread_length

        At full advance the rod is made `lock_preload_margin` longer than the
        just-touching length, so it contacts the shaft *before* the knob
        hard-stops; the remaining bolt travel becomes clamping preload:

              push_rod_length = shaft_flat_z − bolt_tip + lock_preload_margin
        """
        shaft_flat_z = (
            self.depth_lock_bore_depth
            - self.shaft_outer_diameter / 2
            + self.shaft.flat_depth
        )
        bolt_tip = self.depth_lock.bolt_collar_length + self.depth_lock.bolt_thread_length
        return shaft_flat_z - bolt_tip + self.depth_lock.lock_preload_margin

    @computed_field  # type: ignore[prop-decorator]
    @property
    def relief_slot_length(self) -> float:
        """
        Slot runs along Z from the bottom of the shank up to (but not past)
        the shaft cross-bore. Measured against the original tool: slot stops
        at the shaft level, doesn't extend above. So length = length − crossbore_position_from_top.
        """
        return self.shank.length - self.shank.crossbore_position_from_top

    @computed_field  # type: ignore[prop-decorator]
    @property
    def contact_corner_width(self) -> float:
        """§4.3.36 — contact corner is in Y direction (across the working face).

        Slot length is along Z (shank long axis); slot width is across the working
        face in Z; contact corners sit either side of the slot, also in Y. The
        symmetric corner width is (shank.depth − relief_slot_width) / 2.
        """
        return (self.shank.depth - self.shank.relief_slot_width) / 2

    # --- Derived wall thicknesses (§4 critical constraints) ----------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def shaft_wall_around_slot(self) -> float:
        """
        §4.2.13 — wall thickness between the slot's Y edge and the shaft's
        outer surface, measured at the slot's mid-Z plane.

        The slot is open in Z (top and bottom of the shaft — blades drop
        through). The slot extends along X inside the shaft body, with
        end walls handled separately by §4.2.14 (`shaft_wall_around_end_tap`).
        The remaining relevant wall is in the Y direction, taking
        (shaft_outer_diameter − blade_slot_length) / 2 (where
        blade_slot_length is the slot's Y cross-section dim).
        """
        return (self.shaft_outer_diameter - self.shaft.blade_slot_length) / 2

    @computed_field  # type: ignore[prop-decorator]
    @property
    def shank_wall_between_bores(self) -> float:
        """§4.3.23 — wall between crossbore and tapped bore in shank."""
        crossbore_radius = self.crossbore_diameter / 2
        tapped_radius = self.tapped_bore_drill_diameter / 2
        return self.shank.crossbore_to_tapped_bore_gap - crossbore_radius - tapped_radius

    @computed_field  # type: ignore[prop-decorator]
    @property
    def shank_wall_around_crossbore(self) -> float:
        """
        §4.3.24 — min wall around the crossbore in directions perpendicular to bore axis.

        Bore axis is X (along the shaft, normal to working face). Excludes the wall
        toward the tapped bore (+Z direction — that's §4.3.23). Considers:
          - Z down (toward bottom of shank): crossbore_z − crossbore_radius
          - Y either side (assumes bore centred in Y): depth/2 − crossbore_radius
        """
        crossbore_radius = self.crossbore_diameter / 2
        crossbore_z = self.shank.length - self.shank.crossbore_position_from_top
        wall_z_down = crossbore_z - crossbore_radius
        wall_y = self.shank.depth / 2 - crossbore_radius
        return min(wall_z_down, wall_y)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def shank_wall_around_tapped_bore(self) -> float:
        """
        §4.3.25 — min wall around the tapped bore in directions perpendicular to bore axis.

        Excludes the wall toward the crossbore (−Z — that's §4.3.23). Considers:
          - Z up (toward top of shank): tapped_bore_position_from_top − tapped_radius
          - Y either side (assumes bore centred in Y): depth/2 − tapped_radius
        """
        tapped_radius = self.tapped_bore_drill_diameter / 2
        wall_z_up = self.tapped_bore_position_from_top - tapped_radius
        wall_y = self.shank.depth / 2 - tapped_radius
        return min(wall_z_up, wall_y)

    # --- Cross-component invariant validators -------------------------------

    @model_validator(mode="after")
    def _validate_journal_bearing(self) -> "PurflingCutterParams":
        """Integrity of the integral-journal drive-screw bearing:

        1. **Tap wall.** The M2 retaining tap down the journal centre must
           leave ≥ the standard tapped-bore wall (1× thread major radius,
           1 mm floor) of brass around it.
        2. **Thrust shoulder.** The journal must be smaller than the boss so
           the boss face forms a thrust shoulder for the plate.
        3. **Washer retention.** The washer OD must exceed the plate's
           bearing hole, or it can't retain the plate.
        4. **Tap depth.** The journal tap must be at least as deep as the
           captive-screw thread, so the head seats on the journal end face
           before the screw bottoms (that positive seat is what makes the
           play independent of tap depth).
        """
        journal_d = self.drive_screw.bearing_journal_diameter
        tap_major_r = threads.major_radius(self.drive_screw.left_face_tap)
        wall = journal_d / 2 - tap_major_r
        min_wall = max(1.0, tap_major_r)
        if wall < min_wall - 1e-6:
            raise ValueError(
                f"Journal tap wall ({wall:.3f}) < min {min_wall:.3f} mm. "
                f"Increase drive_screw.bearing_journal_diameter (now {journal_d})."
            )

        if journal_d >= self.thumbwheel.boss_diameter:
            raise ValueError(
                f"bearing_journal_diameter ({journal_d}) must be < "
                f"thumbwheel.boss_diameter ({self.thumbwheel.boss_diameter}) so the "
                f"boss face forms a thrust shoulder for the plate."
            )

        if self.captive_washer.outer_diameter <= self.plate_bearing_hole_diameter:
            raise ValueError(
                f"captive_washer.outer_diameter ({self.captive_washer.outer_diameter}) must "
                f"exceed plate_bearing_hole_diameter ({self.plate_bearing_hole_diameter:.3f}) "
                f"to retain the plate."
            )

        if self.drive_screw.left_face_tap_depth < self.captive_screw.thread_length - 1e-6:
            raise ValueError(
                f"left_face_tap_depth ({self.drive_screw.left_face_tap_depth}) must be "
                f"≥ captive_screw.thread_length ({self.captive_screw.thread_length}) so the "
                f"screw head seats on the journal end before the screw bottoms."
            )
        return self

    @model_validator(mode="after")
    def _validate_drive_screw_blade_clearance(self) -> "PurflingCutterParams":
        """The engaged drive-screw thread tip must clear the inboard wall of
        the blade slot by at least `min_clearance`, or a bone-less blade
        dropped into the slot fouls the screw. The shaft length is the lever
        (it moves the slot outboard relative to the screw tip).
        """
        min_clearance = 1.5  # mm, axial — design value, set via shaft.length
        clearance = self.drive_screw_tip_to_slot_clearance
        if clearance < min_clearance - 1e-6:
            raise ValueError(
                f"drive_screw_tip_to_slot_clearance ({clearance:.3f}) < min "
                f"{min_clearance:.3f} mm. The engaged drive-screw tip would foul a "
                f"bone-less blade in the slot. Lengthen shaft.length (currently "
                f"{self.shaft.length}) or shorten the drive-screw stack."
            )
        return self

    @model_validator(mode="after")
    def _validate_depth_lock_sliding_fits(self) -> "PurflingCutterParams":
        """Two sliding-fit clearances inside the depth-lock bore must remain
        positive — otherwise the moving part binds against the bore wall.

        1. **Push rod ↔ smooth bore**. The smooth section of the bore is
           sized at the M6 tap-drill diameter (5.0 mm) because the same
           drill is used for the tapped section below. The rod has to be
           smaller than that to slide.

        2. **Bolt collar ↔ collar bore**. The unthreaded collar between
           the knob and the thread acts as an anti-cocking guide. It needs
           clearance over the matching enlarged section at the bottom of
           the bore.

        Required minimum diametric clearance for both: 0.05 mm (a very
        tight sliding fit). 0 or negative clearance = interference, the
        bolt won't go in.
        """
        min_clearance = 0.05  # diametric

        rod_clearance = self.shank.depth_lock_bore_diameter - self.depth_lock.push_rod_diameter
        if rod_clearance < min_clearance:
            raise ValueError(
                f"Push-rod sliding-fit violated: depth_lock_bore_diameter "
                f"({self.shank.depth_lock_bore_diameter:.3f}) − push_rod_diameter "
                f"({self.depth_lock.push_rod_diameter:.3f}) = {rod_clearance:.3f} mm "
                f"diametric clearance, < min {min_clearance:.3f}. The rod needs to "
                f"be smaller than the bore so it can slide."
            )

        collar_clearance = (
            self.shank.depth_lock_collar_bore_diameter
            - self.depth_lock.bolt_collar_diameter
        )
        if collar_clearance < min_clearance:
            raise ValueError(
                f"Bolt-collar sliding-fit violated: depth_lock_collar_bore_diameter "
                f"({self.shank.depth_lock_collar_bore_diameter:.3f}) − bolt_collar_diameter "
                f"({self.depth_lock.bolt_collar_diameter:.3f}) = {collar_clearance:.3f} mm "
                f"diametric clearance, < min {min_clearance:.3f}. The collar needs to "
                f"be smaller than the matching enlarged bore section."
            )

        # Length margin: bore should be slightly longer than the collar so
        # manufacturing tolerance can't cause the collar's top to land on the
        # tap shoulder.
        min_length_margin = 0.3  # mm — 0.5 design margin, 0.3 floor for tolerance
        length_margin = (
            self.shank.depth_lock_collar_bore_length - self.depth_lock.bolt_collar_length
        )
        if length_margin < min_length_margin:
            raise ValueError(
                f"Collar-bore length margin violated: depth_lock_collar_bore_length "
                f"({self.shank.depth_lock_collar_bore_length:.3f}) − bolt_collar_length "
                f"({self.depth_lock.bolt_collar_length:.3f}) = {length_margin:.3f} mm, "
                f"< min {min_length_margin:.3f}. The bore must be slightly longer than "
                f"the collar."
            )
        return self

    # --- Wall-thickness validators ------------------------------------------

    @model_validator(mode="after")
    def _validate_walls(self) -> "PurflingCutterParams":
        """
        Wall-thickness rules.

        Rules relaxed from the original spec after measuring the real tool —
        the original ≥3 mm / ≥0.6 × D constants were conservative CAD-shop
        guesses; the working brass tool sits closer to 1× thread radius and
        ~0.15 × bore diameter. New rules are: ≥1 mm floor, plus a ratio
        appropriate to the feature.
        """
        # §4.2.13 — wall around blade slot
        min_slot_wall = max(0.8, 1.0 * self.blade.thickness)
        if self.shaft_wall_around_slot < min_slot_wall:
            raise ValueError(
                f"shaft_wall_around_slot ({self.shaft_wall_around_slot:.3f}) "
                f"< min {min_slot_wall:.3f} (§4.2.13)."
            )

        # §4.2.14 wall rule removed: in this tool, the grub-screw end tap
        # opens directly into the slot (no wall). Spec was wrong for this
        # design.

        # §4.3.23 — wall between bores
        min_wall_bb = max(1.2, 1.0 * threads.major_radius(self.drive_screw.thread))
        if self.shank_wall_between_bores < min_wall_bb:
            raise ValueError(
                f"shank_wall_between_bores ({self.shank_wall_between_bores:.3f}) "
                f"< min {min_wall_bb:.3f} (§4.3.23)."
            )

        # §4.3.24 — wall around cross-bore (perpendicular to bore axis)
        min_wall_xb = max(1.0, 0.15 * self.crossbore_diameter)
        if self.shank_wall_around_crossbore < min_wall_xb:
            raise ValueError(
                f"shank_wall_around_crossbore ({self.shank_wall_around_crossbore:.3f}) "
                f"< min {min_wall_xb:.3f} (§4.3.24)."
            )

        # §4.3.25 — wall around tapped bore (perpendicular to bore axis)
        min_wall_tap = max(1.0, 1.0 * threads.major_radius(self.drive_screw.thread))
        if self.shank_wall_around_tapped_bore < min_wall_tap:
            raise ValueError(
                f"shank_wall_around_tapped_bore ({self.shank_wall_around_tapped_bore:.3f}) "
                f"< min {min_wall_tap:.3f} (§4.3.25)."
            )

        return self


__all__ = [
    "BladeParams",
    "CaptiveBearingParams",
    "CaptiveScrewParams",
    "DepthLockParams",
    "DrivePlateParams",
    "DriveScrewParams",
    "GrubScrewParams",
    "MountScrewParams",
    "ProcessConfig",
    "PurflingCutterParams",
    "ShaftParams",
    "ShankParams",
    "SpacerParams",
    "Status",
    "ThumbwheelParams",
    "WasherParams",
]
