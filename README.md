# STEP diff demo

A pull request that changes a part's STEP file gets a comment saying what changed in the part,
with a picture, and which of its [Specify](https://github.com/pzfreo/specify-core-rust)
manufacturing answers still hold.

The part is build123d's
[cast bearing unit](https://github.com/gumyr/build123d/blob/dev/examples/cast_bearing_unit.py)
(Apache-2.0, by Gumyr), an oval flanged housing with a bearing bore and two bolt holes:

| File | What it is |
|---|---|
| `cast_bearing_unit.py` | the build123d model; run it to write the STEP file |
| `cast_bearing_unit.step` | the part, as the pull request changes it |
| `cast_bearing_unit.answers.json` | its Specify answers: material, tolerances, what each hole is for, datum A |
| `.github/workflows/step-diff.yml` | the workflow that compares and comments |

## How it works

On a pull request touching a `.step` file, the workflow downloads the `specify-core` command
line from its release and runs, for each changed part,

```
specify-core diff base.step head.step --answers base.answers.json -o out
```

`diff` matches the two revisions face by face with
[quiddity](https://github.com/pzfreo/quiddity-rust)'s correspondence, so a hole that was
renumbered is still the same hole. Its report gives:

- the part's volume, area, bounding box and face count, before and after;
- each feature added, removed or changed, named as a drawing names it and placed so it can
  be found on the part;
- each answer carried to the new revision, the ones not carried and why, and the ones on a
  changed feature to check;
- the questions the new revision asks that the old one did not;
- the PMI: tolerances, datums and notes in the files, added, removed or changed.

The picture shows the new part with changed faces orange, new ones green and the old part's
removed faces in red. It is pushed to the `step-diff-images` branch, and the comment is
edited in place on each push.

## Try it

Change a dimension in `cast_bearing_unit.py`, run it (`python cast_bearing_unit.py`, with
build123d installed) and open a pull request with the new `cast_bearing_unit.step`.
