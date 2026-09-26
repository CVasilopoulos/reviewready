**In one sentence:** `vc_obj2tifxyz` now writes a `meta.json` `scale` that matches the grid it actually emitted, so a converted mesh renders, flattens and measures at the right size whatever stretch factor, `--uv-downsample`, `--grid-cap` or UV normalization was used.

**One real example:** Starting with PHerc1447 segment `auto_grown_20250703034159599` (tracer output, scale 0.05, 272×185 grid), I ran `vc_tifxyz2obj` on it, converted the OBJ back with `vc_obj2tifxyz seg.obj out --uv-downsample=20`, and rendered the result with `vc_render_tifxyz -g 3 --scale 1`. Before, the render was 34×23 px; after, 680×464 px — the size of rendering the original segment (682×462 px). With normalized UVs and stretch 2000 (the #1319 case), the same render command previously targeted a ~498,000×500,000 px image (killed after 3 minutes, ETA 131 min); after, 678×462 px.

**Before:** `scale` was the UV spacing of the *undecimated* grid — a length, not a density: `--uv-downsample=20` and `--grid-cap` left it at 1.0 while the grid was 20× or 5× sparser, `stretch_factor 2` wrote 0.5 for a grid that has 2 cells per voxel, and normalized UVs got `1/stretch` (#1319 reports 0.0005 instead of ≈0.0865 and `vc_flatten` collapsing to 6×4). `--tifxyz-source` mode copied the source scale but ignored any additional `--uv-downsample`. Everything downstream (`QuadSurface::size()`, `vc_render_tifxyz`, `vc_flatten`, `vc_tifxyz2obj`, the Python `tifxyz` reader) reads `scale` as grid cells per voxel, so those surfaces came out 20× too small, 4× too large, or unusably large.

**After this PR:** `scale` is measured from the emitted grid itself (mean 3D distance between adjacent grid points along each axis, inverted), for metric, normalized and legacy `--uv-non-metric` UVs alike; in `--tifxyz-source` mode the adopted source scale is reduced by the decimation actually applied. `x/y/z.tif` are byte-identical to before — only `meta.json` changes.

**Proof:** same segment, same volume, same renderer settings for every panel (`vc_render_tifxyz -v <level-3 mirror of the PHerc1447 volume> -s <surface> --scale 1 -g 3 -n 1`); look at the render size against the top-left reference.

![vc_obj2tifxyz scale before/after](https://raw.githubusercontent.com/Bullo27/villa/50b77c51b6d6f25f0c6a41924267d9f12425af1a/evidence/obj2tifxyz-scale/evidence_obj2tifxyz_scale.png)

| `vc_obj2tifxyz` arguments | grid | scale before | render before | scale after | render after |
|---|---|---|---|---|---|
| (reference: original tracer segment) | 272×185 | 0.05 | 682×462 | — | — |
| `--uv-downsample=20` | 272×185 | 1.0, 1.0 | 34×23 | 0.04998, 0.04983 | 680×464 |
| `--grid-cap=1000000` | 1085×737 | 1.0, 1.0 | 136×92 | 0.19985, 0.19922 | 679×462 |
| `2` (stretch factor) | 10841×7361 | 0.5, 0.5 | 2710×1840 | 1.9987, 1.9922 | 678×462 |
| normalized UVs (`vc_tifxyz2obj --normalize-uv`), `2000 1.0` as in #1319 | 1994×2001 | 0.0005, 0.0005 | ~498k×500k targeted, killed | 0.3676, 0.5414 | 678×462 |
| (none) | 5421×3681 | 1.0, 1.0 | 678×460 | 0.9993, 0.9961 | 678×462 |
| `--tifxyz-source=<segment>` | 272×185 | 0.05 | 680×462 | 0.05 (unchanged) | 680×462 |
| `--tifxyz-source=<segment> --uv-downsample=20` | 14×10 | 0.05 | 35×25 | 0.00240, 0.00245 | 730×511 |

The last row is one 417-voxel grid cell larger than the reference because `QuadSurface::size()` counts cells, not intervals — pre-existing and negligible at normal densities. All conversions and renders exit 0; `cmp` of `x.tif`/`y.tif`/`z.tif` between the pre-fix and post-fix Release binaries reports no difference (plain and `--uv-downsample=20` conversions checked).

**Why / where this is useful:** anyone who round-trips a segment through OBJ (`vc_tifxyz2obj` → external editing or flattening → `vc_obj2tifxyz`) with a downsample, cap or stretch, or converts a mesh with normalized UVs (#1319), gets a tifxyz that renders and flattens at the right scale instead of one that is silently 20× smaller or too large to render. VC3D's SLIM flatten, the vc3d-mcp flatten tool and `spiral-fitting/render_ink.py` call the tool with `--tifxyz-source` and no extra decimation, so their outputs are unchanged.

- [x] Verified by running the example and proof above on my machine on the stated data (AI-assisted; see disclosure).

## Details

Fixes #1319 (report and the "write the scale measured from the grid actually produced" suggestion: @Aleredfer). Same approach as #1391 by @olgaiv39, which was auto-closed for inactivity on 2026-08-28 after @pmh47's review points were addressed and @hendrikschilling asked for regression coverage of `--uv-downsample`, `--tifxyz-source` scale preservation, varying `stretch_factor` and a direct check against the emitted TIFF grid. This PR supplies exactly that coverage in one 200-line test and keeps the code change small.

**What changed** (`vc_obj2tifxyz.cpp`: +45/−39 lines):
- `createQuadSurface()`: for every non-source mode, measure the emitted grid's mean 3D spacing per axis (the existing `calculateScaleFromGrid`) and write `1 / spacing`; fail with a clear error instead of writing an invalid scale if nothing was measurable. The old metric-mode formula (`uv_range / (gw_raw - 1) * uv_to_obj`, then `* mesh_units`) is gone.
- `--tifxyz-source` mode: `scale = src_scale * (decimated_cols - 1) / (source_cols - 1)` — verbatim when undecimated.
- `mesh_units` is still accepted but no longer affects `scale` (OBJ coordinates are voxel coordinates; the argument was multiplying a density by µm-per-unit). Usage text updated.
- `lasagna/tifxyz_format.md` §2/§5.1: `scale` is grid cells per voxel, adjacent vertices are `1/scale` voxels apart, doubling the cell spacing halves `scale` (the text described it as a spacing).
- New `core/test/test_obj2tifxyz_cli.cpp` (label `vc-core`, registered like `test_tifxyz_selfcross_cli`): a flat 41×31 mesh with 20-voxel cells, 7 conversions (plain, `--uv-downsample=20`, `--grid-cap`, stretch 2, normalized UVs with stretch 40, `--tifxyz-source` with and without `--uv-downsample=4`), each checked for column count, `scale == (cols-1)/extent`, `size()` within one cell of the extent, and adjacent-point 3D distance `== 1/scale` read back from the written tifxyz. On the unpatched binary 30 checks fail in exactly the 5 affected conversions; plain and pure-source pass before and after.

**Tested:** commit d7d099d, Ubuntu 24.04.4, gcc 13.3.0, ASan+UBSan Debug build: the full `vc-core` label — 143/143 tests including the new one — passes; `test_quadsurface_fixtures` is unaffected because the committed fixture keeps its pre-fix baked scale (0.0078125) and the test reads the file. Real-data runs above used a Release build.

**Not changed:** the legacy `--uv-non-metric` grid *sizing* (only its final `scale` now goes through the same measurement); `QuadSurface::resample`'s handling of `_scale` (separate); #1630's degenerate-output handling (adjacent hunks of the same file, no overlap).

**From the author:** I contribute to VC through an AI-assisted workflow (Claude, directed by me), and this fix came out of running the command-line tools end to end on a PHerc1447 segment rather than from searching the code for bugs: the tifxyz written by `vc_obj2tifxyz` looked fine but rendered at the wrong size whenever a downsample, cap or stretch was used. Checking for duplicates showed that #1319 had already reported it and that #1391 had a fix the maintainers were ready to consider merging before it went stale, so this PR picks that up and adds the regression coverage that was asked for. I care about this path because the OBJ round-trip is how externally flattened or edited meshes get back into VC3D, and a wrong `scale` silently breaks everything downstream while the surface data itself looks correct. I reviewed the investigation, the issue history and the evidence; every number in this PR was produced by running the stated commands on my machine.

**AI disclosure:** investigation, patch, test and this write-up were produced with Claude (Anthropic) under my direction; every number above comes from running the stated commands on the stated data on my machine.
