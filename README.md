# STEP diff demo

When a pull request changes a part's STEP file, it gets a comment that says what changed in the part,
shows a picture of the change, and carries the part's [Specify](https://github.com/pzfreo/specify-core-rust)
manufacturing answers to the new revision. This repository shows it working, and is a template for
setting it up on your own parts.

**See it:** [pull request #2](https://github.com/pzfreo/step-diff-demo/pull/2) makes the flange 2 mm
thicker and the bolt holes 1 mm smaller. This is the comment the workflow posted on it; its
picture and its "Turn the part round in 3D" link open the part in the browser:

![The STEP diff comment on pull request #2](docs/comment.png)

The comment shows:

- **the summary:** two holes changed, and the rounds and surfaces around them moved with them;
- **the picture:** the new part, with changed faces in orange and the old part's faces in translucent red;
- **the measures:** volume, area and bounding box, before and after;
- **what changed:** each feature, named and placed so it can be found on the part, then what
  happened to it: "depth 11 → 13; diameter 10 → 9";
- **answers to check:** the M8 clearance and the position tolerance are on the holes that changed,
  so they're flagged;
- **the carried answers:** in a fold, ready to commit for the new revision.

### An assembly

**See it:** [pull request #DEMO](https://github.com/pzfreo/step-diff-demo/pull/DEMO) changes two of
gramil's twelve parts: the shaft's tapped mount holes go 1 mm deeper, and the drive plate's mount
hole goes from Ø2.2 to Ø2.4. Its comment lists the parts that changed, gives each its own "what
changed", and pictures the whole assembly with the changed parts in orange. Its links open the
assembly in 3D, or one part of it.

## Do the same in your repository

1. **Add the workflow.** Copy [`.github/workflows/step-diff.yml`](.github/workflows/step-diff.yml)
   into your repository at the same path and commit it to your default branch. It's one step:

   ```yaml
       steps:
         - uses: pzfreo/specify-core-rust/step-diff@main
   ```

   There's nothing to install and no secret to set; the job's own token is enough.

2. **Commit your parts as STEP files**, wherever you keep them. Each pull request that changes one
   gets the comment, and later pushes update the same comment.

3. **Add answers, if you want them carried (optional).** The answers are the decisions about the
   part: material, tolerances, what each hole is for, datums. Either:
   - **Export the STEP with Specify.** Use the Specify editor at [draftwright.io](https://draftwright.io),
     or `specify-core write`. The answers are stored in the STEP file and carried with no extra
     file.
   - **Keep an answers file beside the part.** For `bracket.step`, that's `bracket.answers.json`, as
     [`cast_bearing_unit.answers.json`](cast_bearing_unit.answers.json) is here.

   Without answers, the comment still shows what changed, the picture and the measures.

That's all. The action's [guide](https://github.com/pzfreo/specify-core-rust/blob/main/step-diff/README.md)
covers its options, what it compares, where the pictures go and its limits, forks among them.
Assemblies are compared part by part, the parts paired by name. [How `diff` works](https://github.com/pzfreo/specify-core-rust/blob/main/docs/diff.md)
explains how the two revisions are matched and what each part of the comment means.

## Try it here

A pull request from a fork gets a read-only token, so the workflow can't comment on it. To try it
yourself, use this repository as a template (or fork it), turn on Actions in your copy, and open a
pull request within your copy:

1. Change a dimension in `cast_bearing_unit.py`, for example the flange thickness `A1`.
2. Run `python cast_bearing_unit.py`, with [build123d](https://github.com/gumyr/build123d)
   installed. It rewrites `cast_bearing_unit.step`.
3. Commit the new STEP file on a branch and open a pull request.

## What's here

| File | What it is |
|---|---|
| `cast_bearing_unit.py` | the build123d model; run it to write the STEP file |
| `cast_bearing_unit.step` | the part |
| `cast_bearing_unit.answers.json` | its Specify answers: material, tolerances, what each hole is for, datum A |
| `gramil/` | gramil's model, a purfling cutter in twelve parts (pzfreo/gramil) |
| `gramil_assembly.py` | builds `gramil_assembly.step` from it |
| `gramil_assembly.step` | the assembly |
| `.github/workflows/step-diff.yml` | the workflow that compares and comments |

The part is build123d's
[cast bearing unit](https://github.com/gumyr/build123d/blob/dev/examples/cast_bearing_unit.py)
(Apache-2.0, by Gumyr): an oval flanged housing with a bearing bore and two bolt holes.

The assembly is [gramil](https://github.com/pzfreo/gramil), a purfling cutter for violin making.
`gramil/`, `gramil_assembly.py` and `gramil_assembly.step` are under the Open Community License v1
([`gramil/LICENSE`](gramil/LICENSE)), not this repository's Apache-2.0. `gramil/` holds the parts of
gramil's model the assembly needs, as gramil has them but for two dimensions set to an earlier
revision's: the pull request changes them to gramil's own.
