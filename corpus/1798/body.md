**In one sentence:** When grid-guided growth asks for a normal-grid level the store cannot provide, the log now says so and names the level actually used, instead of falling back silently.

**One real example:** Starting with the published PHercParis4 normal-grid store `20260411134726-surface-20260413141734-surface-recto-2um-ps256-L0-th0.45.normal-grids` and its surface prediction zarr, I grew a seed at `20496 20483 10140` with `"normal_grid_level": 2`, and it produced `warning: normal_grid_level=2 ignored; store at ... is single-scale ...; using level 0` right before the usual `Loaded normal grid level 0` line.

**Before:** `NormalGridVolume` ignores `normal_grid_level` for a single-scale store and clamps an out-of-range level for a multiscale store, both without a message. The only hint is `Loaded normal grid level N`. That is what #1776 reports: level 2 or 3 was requested to make grid-guided growth faster, and nothing said the setting had no effect. The published PHercParis4 normal-grid store is single-scale.

**After this PR:** Both cases print one warning on stderr with the requested level, the store path and the level used. The single-scale warning also says that `vc_gen_normalgrids pyramid` can derive a multiscale store from a local copy. The fallback is unchanged and nothing throws, so growth on single-scale stores keeps working and produces the same surface.

**Proof:** Upstream main `bcf631dd3` against this branch on the same base, with the same data, params and seed, CPU only. The attached images show the evidence script's terminal output, rendered from its log. Its output is filtered to the seed, warning, load and result lines. The `params:`, `EXIT=` and `--` lines are printed by the script. Look at the line after `seed location` in each pair. The unfiltered main run for case 1 prints no warning of any kind either.

<img width="4488" height="1136" alt="1776-single-scale" src="https://github.com/user-attachments/assets/2d3ce381-5e5a-44a7-9f91-02d945c7a7be" />

<img width="2472" height="1928" alt="1776-multiscale-and-tests" src="https://github.com/user-attachments/assets/bafb1860-a203-462a-a1b3-c193b046d87d" />

The published store's `metadata.json` has no `format` key, so it is single-scale:
```
{"chunk-budget-mib":4100,"debug-per-slice":true,"grid-step":64,"input-level":0,"io-threads":128,"preview-every":100,"prune-min-length-px":80.0,"sparse-volume":1,"spiral-step":20.0,"verify-grid-save":false}
```

1. Published single-scale store, `normal_grid_level=2`

Before (main):
```
params: {"normal_grid_path": "/out/ev1776/ngrids-remote", "normal_grid_level": 2, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
Loaded normal grid level 0 (coordinate_scale=1, output_spiral_step=20)
generated surface 400.707240 vx^2 (0.000023 cm^2)
EXIT=0
```
After (this PR):
```
params: {"normal_grid_path": "/out/ev1776/ngrids-remote", "normal_grid_level": 2, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
warning: normal_grid_level=2 ignored; store at /out/ev1776/ngrids-remote is single-scale (no "format":"normal-grid-multiscale" in metadata.json); using level 0. A multiscale store can be derived from a local copy with vc_gen_normalgrids pyramid -i <store> -o <multiscale store>
Loaded normal grid level 0 (coordinate_scale=1, output_spiral_step=20)
generated surface 400.707240 vx^2 (0.000023 cm^2)
EXIT=0
```
After (this PR), `normal_grid_level=0`, no warning:
```
params: {"normal_grid_path": "/out/ev1776/ngrids-remote", "normal_grid_level": 0, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
Loaded normal grid level 0 (coordinate_scale=1, output_spiral_step=20)
generated surface 400.707240 vx^2 (0.000023 cm^2)
EXIT=0
```

2. Multiscale store with levels 0..1, `normal_grid_level=3`

The store was built with `vc_gen_normalgrids pyramid --min-level 0 --max-level 1` from 6 published grid files at the seed slices (xy 010140 and 010142, xz 020482 and 020484, yz 020496 and 020498):
```
Pyramid complete: "/out/ev1776/ngrids-ms"
multiscale metadata.json: "format":"normal-grid-multiscale" "max-level":1 "min-level":0
```
Before (main):
```
params: {"normal_grid_path": "/out/ev1776/ngrids-ms", "normal_grid_level": 3, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
Loaded normal grid level 1 (coordinate_scale=0.5, output_spiral_step=20)
generated surface 403.850831 vx^2 (0.000023 cm^2)
EXIT=0
```
After (this PR):
```
params: {"normal_grid_path": "/out/ev1776/ngrids-ms", "normal_grid_level": 3, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
warning: normal_grid_level=3 is outside the levels 0..1 available in /out/ev1776/ngrids-ms; using level 1
Loaded normal grid level 1 (coordinate_scale=0.5, output_spiral_step=20)
generated surface 403.850831 vx^2 (0.000023 cm^2)
EXIT=0
```
After (this PR), `normal_grid_level=1`, no warning:
```
params: {"normal_grid_path": "/out/ev1776/ngrids-ms", "normal_grid_level": 1, "generations": 2, "min_area_cm": 0, "thread_limit": 8, "use_cuda": false}
seed location [20496, 20483, 10140] value is 255
Loaded normal grid level 1 (coordinate_scale=0.5, output_spiral_step=20)
generated surface 403.850831 vx^2 (0.000023 cm^2)
EXIT=0
```

3. Doctests, `test_normal_grid_volume`
```
-- BEFORE
9 test case(s) passed
-- AFTER
11 test case(s) passed
```

**Why / where this is useful:**

I picked this up because asking for a coarser normal-grid level on the published PHercParis4 store silently gave level 0, and nothing in the log said so. I ran growth before and after on the published grids and on a small multiscale store built from them, and checked that the warning appears and the generated surface is unchanged.

`vc_grow_seg_from_seed` and VC3D growth use normal grids to steer the traced surface. The published PHercParis4 normal-grid store is single-scale. Anyone who raises the level to speed up growth, as in #1776, gets full-resolution grids with no explanation. With the warning they see right away that the store cannot serve that level, and how to build one that can. VC3D growth with Growth scale above 0 on a single-scale store prints the same warning in its log. Runs at a level the store has print nothing new.

- [x] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

### What changed

- `volume-cartographer/core/src/NormalGridVolume.cpp`: two `std::cerr` warnings in the constructor. One is in the single-scale branch when `requested_level != 0`. The other is in the multiscale branch, after the existing `std::clamp`, when the clamped level differs from the request. Level selection is unchanged and nothing new throws.
- `volume-cartographer/core/test/test_normal_grid_volume.cpp`: two doctests. They reuse `makeEmptyNgvDir`, add a multiscale `metadata.json` fixture with the keys `vc_gen_normalgrids pyramid` writes (`format`, `min-level`, `max-level`, `source-metadata`), and capture stderr with an `rdbuf` swap.
  - Single-scale store: level 2 warns and uses 0, level 0 is silent.
  - Multiscale 0..1: level 3 warns and uses 1, level 1 is silent.
  - Multiscale 1..2: level 0 warns and uses 1.

### Why a warning and not an error

The fallback returns valid grids, and the surfaces above are identical with and without this PR. Throwing would break VC3D growth on the published single-scale store whenever Growth scale is above 0, because `SegmentationGrower.cpp` passes Growth scale as `normal_grid_level`.

### Tested

- Base: upstream main `bcf631dd3`. The branch was then rebased onto `4b3c72882`. Neither touched file changed in between, so both files are byte-identical to the tested ones.
- Linux x86_64 only, in `ghcr.io/scrollprize/villa/volume-cartographer:builder-ubuntu-26.04`, cmake preset `ci-release-gcc` with `-DVC_TESTING=ON`, CPU only. Not tested on macOS or Windows.
- Normal grids: `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/representations/predictions/surfaces/20260411134726-surface-20260413141734-surface-recto-2um-ps256-L0-th0.45.normal-grids`, streamed through a `normal-grids-remote.json` marker (`{"url": "<store>"}`) in the `normal_grid_path` directory. 237 MB of grid files were fetched for the single-scale runs.
- Volume: `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/representations/predictions/surfaces/20260411134726-surface-20260413141734-surface-recto-2um-ps256-L0-th0.45.zarr`, the surface prediction the grids were made from (voxel size 2.4). The seed `20496 20483 10140` has value 255 and populated grids on all three planes.
- Growth: `vc_grow_seg_from_seed -v <volume> -t <out> -p <params.json> -s 20496 20483 10140` with the params shown in each block.
- Multiscale store: `vc_gen_normalgrids pyramid -i <6 grid files + metadata.json> -o <store> --min-level 0 --max-level 1 --no-images` (23 MB).
- Doctests: `test_normal_grid_volume`.

### Limitations

- `GrowPatch.cpp` clamps the level to 0..5 before it constructs `NormalGridVolume`, and VC3D clamps Growth scale to 0..5. A request for 8 is therefore reported as `normal_grid_level=5`, and on a store with levels above 5 it is still capped without a message. I left that clamp alone to keep this change to the two silent fallbacks in `NormalGridVolume`. I can remove it here if you prefer.
- For a streamed store, the path in the warning is the local `normal_grid_path` directory that holds the marker, not the remote URL.
- I did not run the new doctests against main. Main has no warning text, so their `warning.find` checks would fail there.

### Prior work and credit

- @rodriguescarson reported #1776 and proposed the single-scale warning. The single-scale branch uses his proposal, with the `vc_gen_normalgrids pyramid` hint added, and he is a co-author of the commit.
- #921 (@bruniss, `3a2a2af47`) added multiscale normal-grid stores and level selection in `NormalGridVolume`.
- #1344 (@Bullo27, `4386f625e`) made a missing scale level fail fast in the apps instead of falling back silently. Here the fallback returns correct grids, so this PR only warns.
- No other PR or branch addresses this. Open PR #1681 changes `NormalGridVolume.cpp` for cache budgeting only. This patch applies on top of it with a line offset and no conflict.

AI-assisted (Claude Code), human-directed. All runs above were executed on real data, not inferred.
Fixes #1776

