**In one sentence:** You can convert a published `paths/` OBJ with `vc_obj2tifxyz` and flatten the result at its true size, and a conversion that produced nothing, or only a 2 x 2 grid, now fails instead of reporting success.

**One real example:** Starting with the published Scroll 1 segment mesh `PHercParis4.volpkg/paths/20231007101619/20231007101619.obj` (1,521,895 vertices, UVs normalised to [0,1]), I ran `vc_obj2tifxyz 20231007101619.obj out 2000 1.0`, and it produced a 2001 x 2001 tifxyz (3,532,144 valid points) whose `meta.json` now stores `scale: [0.0602, 0.1244]`, matching the measured 16.6 x 8.0 voxel spacing of its samples; `vc_flatten` on that output produced a 961 x 4113 grid with 3,485,607 valid points.

**Before:** The same command wrote `scale: [0.0005, 0.0005]`, the UV step, which is the inverse of the format's convention (a tracer patch grown at step 20 stores 0.05, and `vc_flatten`, `vesuvius.tifxyz` and `Tifxyz.full_resolution_shape` all size their output as extent x scale). `vc_flatten` sized its output from that value and collapsed the whole segment to a 9 x 18 grid with 159 points (#1319). With no stretch factor the tool built a 2 x 2 grid, rasterized 0 points, printed "Successfully converted to tifxyz format" and exited 0, leaving a directory whose bbox is all `-1` (#1320). In `--tifxyz-source` mode the source scale was copied as is, even when `--uv-downsample` made the grid sparser.

**After this PR:**

- `scale` is measured on the grid actually written, after any decimation, and stored as its reciprocal per axis. This applies to the UV-metric and the non-metric mode.
- `--tifxyz-source` mode keeps the source scale when nothing is decimated, so the VC3D flatten flow is unchanged. With decimation it writes `src_scale * (decimated_cols - 1) / (source_cols - 1)` per axis.
- `mesh_units` is still accepted but no longer changes `scale`, because the measured spacing is already in voxels.
- Zero valid grid points is an error, and so is any 2 x 2 output grid, even one with valid corners: exit 1, nothing written. A 2 x 2 grid is the clamped minimum, so it is degenerate whatever else the user passes. The errors print no hint. The first commit's hint named `--uv-to-obj`, which @bruniss asked #1630 to stop recommending (see Prior work). It never changes the grid size, because the UV-metric grid is `ceil(uv_range * stretch_factor) + 1`. The help text still explains that normalised UVs need a `stretch_factor` such as 800.
- The help text no longer calls the default invocation "legacy behavior", and it says the tool exits non-zero when no grid point is rasterized or the output grid is only 2 x 2. `lasagna/tifxyz_format.md` now defines `scale` as grid cells per voxel and drops the two bullets that contradicted that definition.
- New opt-in end-to-end test `test_obj2tifxyz_e2e` (`VC_RUN_E2E=1`) on synthetic meshes covers the empty grid, the 2 x 2 grid, the measured scale, grid size and scale across `stretch_factor`, the decimated scale, `mesh_units`, and source-scale mode with and without decimation.

**Proof:** Same data and commands on both sides of each comparison. Look at the `scale` each run prints and writes to `meta.json`, the exit codes of the default invocation and the 2 x 2 window, and the `vc_flatten` output grid size. The two screenshots below are from the upstream vs `69a1c530b` runs. The text blocks after them are copied terminal output.

<img width="2254" height="876" alt="Screenshot 2026-09-14 at 10 54 19 PM" src="https://github.com/user-attachments/assets/610fed56-7adf-426e-b95d-625d4892170f" />

<img width="2259" height="795" alt="Screenshot 2026-09-14 at 10 54 39 PM" src="https://github.com/user-attachments/assets/8a4de1df-4750-4947-8e02-897a31f0e406" />

<img width="1958" height="986" alt="Screenshot 2026-09-15 at 9 57 12 AM" src="https://github.com/user-attachments/assets/dffa8b4b-a032-4088-b935-a457abe1aac5" />

<img width="2136" height="1182" alt="Screenshot 2026-09-15 at 9 57 40 AM" src="https://github.com/user-attachments/assets/9b16285d-54a6-43c1-9b9e-9b61c1295f6c" />

In the first four blocks, "before" is `vc_obj2tifxyz` built from upstream `d82e13edf` and "after" is `69a1c530b` as first pushed.

Default invocation (#1320):

```
# before
UV-metric mode: grid 2 x 2  scale(OBJ units): 1, 1
Warning: no valid grid points were rasterized.
Valid grid points: 0 / 4 (0%)
Successfully converted to tifxyz format
EXIT=0        meta.json: scale [1.0, 1.0], bbox [[-1,-1,-1],[-1,-1,-1]]

# after (69a1c530b; the follow-up commit drops the Hint line)
Error: no valid grid points were rasterized (grid 2 x 2); refusing to write an empty tifxyz.
Hint: the UVs span 1 x 1 (normalised to [0,1]), so at the default stretch_factor of 1 the grid has no room for any sample. Pass a stretch_factor (e.g. 800) to set the grid resolution, or --uv-to-obj=<OBJ units per UV unit> if the UVs are metric.
Failed to create quad surface
EXIT=1        (no output directory)
```

`2000 1.0` (#1319):

```
# before
Valid grid points: 3532144 / 4004001 (88.2154%)
Scale from UV (micrometers): 0.0005, 0.0005

# after
Valid grid points: 3532144 / 4004001 (88.2154%)
Measured cell spacing: 16.6178, 8.03642 OBJ units -> scale: 0.0601765, 0.124434 cells per unit
```

Independent check with numpy/tifffile (mean distance between adjacent valid samples; the x/y/z grids of the two runs are byte-identical, only `meta.json` differs):

```
before: written scale 0.0005, 0.0005   -> implies 2000 voxels per cell
        measured spacing x 16.613 (median 16.609), y 8.034 (median 8.036) voxels per cell
after:  written scale 0.0601765, 0.124434 -> implies 16.62, 8.036 voxels per cell
        measured spacing x 16.613, y 8.034
```

Downstream, `vc_flatten -i <out> -o <flat> --downsample 4` on each output:

```
before:  Creating output grid 9 x 18 (input scale=0.0005x0.0005, UV range=15941.6x33037.9)   Valid points: 159
after:   Creating output grid 961 x 4113 (input scale=0.0601765x0.124434, UV range=15941.6x33037.9)   Valid points: 3485607
```

Apart from refusing 2 x 2 grids, the follow-up commit changes only the written `scale`, never the x/y/z grids. On it, `2000 1.0` writes the identical scale 0.0601765, 0.124434. The default invocation was re-run on it (see the paragraph after the 2 x 2 window block). `vc_flatten` was not.

In the remaining blocks, "before" is `69a1c530b` and "after" is the follow-up commit.

`2000 7.91`, with `mesh_units` set to the Scroll 1 voxel size:

```
before: written scale 0.00760764, 0.0157312 -> implies 131.4, 63.57 voxels per cell
after:  written scale 0.0601765, 0.124434   -> implies 16.62, 8.036 voxels per cell
        measured spacing x 16.613 (median 16.609), y 8.034 (median 8.036) -> matching scale 0.06020, 0.12448
        x/y/z grids identical between the two runs
```

Source-scale mode on the published tifxyz `20231007101619-on-20260310170716-45.532um.tifxyz` (scale 0.05), converted with `vc_tifxyz2obj` and back with `--tifxyz-source=<that dir>`:

```
no decimation:      before 0.05, 0.05   after 0.05, 0.05
                    measured spacing x 19.9 (median 19.96), y 19.5 (median 19.70) voxels

--uv-downsample=4:  grid 72 x 35
                    before 0.05, 0.05       -> implies 20 voxels per cell
                    after  0.0125, 0.0125   -> implies 80 voxels per cell
                    measured spacing x 77.48 (median 79.06), y 75.08 (median 76.50) -> matching scale 0.01291, 0.01332
```

2 x 2 grid on real data: a fully valid 30 x 30 window (900 of 900 points) of the same published tifxyz, exported with `vc_tifxyz2obj <window> <obj> --normalize-uv` and converted back with `vc_obj2tifxyz <obj> <out>` at the default stretch:

```
# before
UV-metric mode: grid 2 x 2  UV-derived cell spacing (OBJ units): 1, 1
Valid grid points: 1 / 4 (25%)
Successfully converted to tifxyz format
EXIT=0        wrote a 2 x 2 tifxyz, scale [1.0, 1.0]

# after
UV-metric mode: grid 2 x 2  UV-derived cell spacing (OBJ units): 1, 1
Valid grid points: 1 / 4 (25%)
Error: degenerate 2 x 2 output grid (1 of 4 points rasterized); refusing to write a tifxyz.
Failed to create quad surface
EXIT=1        (nothing written)
```

Default invocation on `20231007101619.obj` (0 of 4 rasterized): both exit 1 and write nothing. `69a1c530b` prints the error and the Hint line shown above. The follow-up prints the same error with no Hint line.

The e2e test: against the `69a1c530b` binary, 6 checks fail (2 each in the `mesh_units` and the source-scale decimation subcases, and 2 in the 2 x 2 subcase). Against the follow-up commit: `1 test case(s) passed`.

**Why / where this is useful:** Anyone converting a published OBJ (all the `paths/` meshes carry normalised UVs) or a mesh produced outside VC3D into tifxyz, to flatten it with `vc_flatten`, render it with `vc_render_tifxyz`, or read it with `vesuvius.tifxyz`. Scripts that drive the tool no longer mistake an empty or 2 x 2 conversion for success. `mesh_units` no longer changes the scale, and a round trip through OBJ with `--tifxyz-source` plus `--uv-downsample` gets a scale that matches the sparser grid. The older `CWindowContextMenu` flatten path (`--uv-downsample=20`, no `--tifxyz-source`) previously got scale 1.0 for a 20-voxel grid and now gets 0.05, the value the rest of the pipeline expects for that spacing.

> [Christos: I picked up #1319 and #1320 because I wanted a working way to turn the published Scroll 1 paths/ meshes into tifxyz and flatten them. With the current tool, that path silently produces an empty or collapsed surface. I reproduced both bugs myself on 20231007101619.obj before changing anything, and I compared the before and after runs in the screenshots above, including the vc_flatten output size. I read through the diff to vc_obj2tifxyz.cpp [and checked that the scale now matches the measured sample spacing]. When I found the three earlier PRs, I credited them and brought in the parts of their fixes that mine was missing.

- [x] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Tested commits: `69a1c530b` and the follow-up commit directly on top of it, based on upstream `d82e13edf`. Built with `cmake --preset ci-release-gcc` inside `ghcr.io/scrollprize/villa/volume-cartographer:builder-ubuntu-26.04`, Linux x86_64.
- Data: `https://dl.ash2txt.org/full-scrolls/Scroll1/PHercParis4.volpkg/paths/20231007101619/20231007101619.obj` (311.8 MiB), and the published tifxyz `PHercParis4/segments/20231007101619/mesh/20231007101619-on-20260310170716-45.532um.tifxyz` (285 x 137 grid, cols x rows, scale 0.05), plus a fully valid 30 x 30 window of it.
- Commands: `vc_obj2tifxyz mesh.obj out-default` and `vc_obj2tifxyz mesh.obj out-2000 2000 1.0` with upstream `d82e13edf`, `69a1c530b` and the follow-up commit; `vc_obj2tifxyz mesh.obj out-units 2000 7.91` with `69a1c530b` and the follow-up commit; `vc_flatten -i out-2000 -o flat --downsample 4` on the upstream and `69a1c530b` outputs; the tifxyz converted with `vc_tifxyz2obj` (UVs = grid index / scale) and back with `vc_obj2tifxyz seg.obj out --tifxyz-source=<tifxyz dir>`, with and without `--uv-downsample=4`, on `69a1c530b` and the follow-up commit; the 30 x 30 window exported with `vc_tifxyz2obj <window> <obj> --normalize-uv` and converted back with `vc_obj2tifxyz <obj> <out>` on `69a1c530b` and the follow-up commit. Spacing measured with a short numpy/tifffile script (mean and median of adjacent-sample distances along x and y over valid pairs).
- The measured scale is anisotropic here (0.060 vs 0.124) because a non-square surface normalised into a [0,1] square and rasterized on a square grid has different spacing per axis. tifxyz carries a per-axis scale and `vc_flatten` honours it per axis, so it is reported rather than averaged; the geometric mean, 0.0865, is the single figure #1319 measured.
- `mesh_units` is accepted for compatibility and not used for `scale`. Upstream multiplied the scale by it, and this PR's first commit divided by it. The measured spacing is already in voxels.
- Limitation: spacing is a mean over the grid interior (borders skipped, every 4th sample on grids of 20+ cells). On a grid too sparse to measure, the tool falls back to the UV-derived estimate with a warning; if that is not positive either, it exits non-zero. A 2 x 2 grid is refused however many points it rasterizes. A grid with 2 points on one axis and more on the other is still written.

### Prior work

Three earlier PRs worked on these issues and none was merged. All three got there before this PR, and it overlaps with each of them. The follow-up commit adopts #1683's source-scale and `mesh_units` handling, with Matteo as co-author, and #1630's refusal of every 2 x 2 grid without a hint, with Anay as co-author.

- **#1391 by Olga Ivanova (@olgaiv39)** (opened 2026-08-11, auto-closed for inactivity 2026-08-28). It measured `scale` from the emitted grid and wrote `1 / spacing`, kept `mesh_units` out of it, left `--tifxyz-source` unchanged, and corrected `tifxyz_format.md`. @pmh47 said it would be considered for merge once his review points were addressed, and Olga addressed them. @hendrikschilling then said the change looked fine apart from test coverage. He asked for tests of `--uv-downsample`, `--tifxyz-source` scale preservation, varying `stretch_factor`, and a check against the emitted grid. Her remaining test covered normalised UVs, anisotropic spacing and `mesh_units` independence. This PR's scale change is the same fix. The test here now has a subcase for each of his points. The `stretch_factor` subcase runs stretch 20 and 80 and checks the size of the written `x.tif` and the scale.
- **#1630 by @AnayGarodia** (opened 2026-08-28, auto-closed 2026-09-13). It fixed #1320 with before/after on the published Scroll 1 mesh `paths/20230503225234` and a metric-UV control: exit non-zero when nothing is rasterized, and a corrected "legacy behavior" help label. @Bullo27 reproduced the bug there with a quad whose UVs form a diamond, so no bounding-box corner is covered. This PR's empty-grid test uses the same idea. @Bullo27 later reported a normalised-UV mesh that fills 1 of the 4 corners and slips past a zero-only check. Anay then refused every 2 x 2 grid, since a 2 x 2 grid is the clamped minimum and comes out degenerate whatever the user passes next. After that, @bruniss asked #1630 to stop recommending `--uv-to-obj`, since a 2 x 2 grid still fails with it, and to just report the invalid output. Anay dropped the flag suggestion. The #1320 part of this PR's first commit matched #1630's first commit. The follow-up commit takes the later changes too: it refuses every 2 x 2 grid and prints no hint.
- **#1683 by Matteo Bulloni (@Bullo27)** (opened 2026-09-02, closed by its author 2026-09-10, not reviewed). It took the same core approach for #1319 and credited #1391. It also reduced the `--tifxyz-source` scale by the decimation applied, stopped using `mesh_units` for the scale, updated `tifxyz_format.md`, and added a 7-conversion CLI test that reads each written grid back, with render evidence on a PHerc1447 segment. The follow-up commit here adopts both behaviours and #1683's wording for the definition of `scale` and the resampling rule.
- **Where this PR differs:** #1319 and #1320 are fixed in one change. It has before/after on a published Scroll 1 `paths/` mesh through `vc_flatten`, the pipeline #1319 reported. When the grid is too sparse to measure, it falls back to the UV-derived estimate with a warning, where #1391 and #1683 exit with an error. The source-scale subcases repeat #1683's scenarios, including `--uv-downsample=4`, and the `mesh_units` subcase covers the same check as #1391's final test. Unlike #1683's test, it does not vary `--grid-cap`, and it reads back only the size of `x.tif`, not the x/y/z values.

AI-assisted (Claude Code), human-directed. The conversions and flattening above ran on the stated Scroll 1 data. The e2e test uses synthetic meshes.

Fixes #1319
Fixes #1320

