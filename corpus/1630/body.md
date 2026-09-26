Fixes #1320

## Motivation

I was converting some of the path segments to feed into the render + ink steps when, with default args, the tool wrote full -1 output and still said "Successfully converted" with exit 0. This fix makes it fail loudly and say which flag to pass instead.

## What changed

- Exit non-zero when zero grid points were rasterized, before any output is written (previously: warning to stderr, then "Successfully converted", exit 0, and an all-sentinel `x/y/z.tif` + `bbox [[-1,-1,-1],[-1,-1,-1]]`).
- When the UV range looks normalized (<= 1.5 per axis), say so and name the flags that make the conversion work (explicit `stretch_factor` or `--uv-to-obj`).
- Fix the `--help` example labeled "(legacy behavior)" — the plain invocation actually runs in the default UV-metric mode.

## Evidence on real scroll data

Segment `PHercParis4.volpkg/paths/20230503225234` (normalized-UV OBJ, dl.ash2txt.org); control: `PHercParis4/segments/20260602204401-5753_-7` (metric-UV OBJ, s3 open-data bucket). Built and run on macOS arm64 (`scripts/build_macos.sh`).

**Before (main):** default args -> `Valid grid points: 0 / 4 (0%)` -> "Successfully converted", exit 0, output dir contains only -1 sentinels.

![1320-before.png](https://raw.githubusercontent.com/AnayGarodia/villa/evidence-assets/screenshots/1320-before.png)

**After (this branch):**
- default args -> error naming the problem and the flags, exit 1, no output written
- `--uv-non-metric` (issue case 2) -> same error, exit 1
- explicit `stretch_factor 800` -> `Valid grid points: 503348 / 641601 (78.45%)`, real bbox, exit 0
- metric-UV control -> `26585600 / 45470061 (58.47%)`, converts exactly as before, exit 0

![1320-after-1.png](https://raw.githubusercontent.com/AnayGarodia/villa/evidence-assets/screenshots/1320-after-1.png)
![1320-after-2.png](https://raw.githubusercontent.com/AnayGarodia/villa/evidence-assets/screenshots/1320-after-2.png)
![1320-after-3.png](https://raw.githubusercontent.com/AnayGarodia/villa/evidence-assets/screenshots/1320-after-3.png)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_0189NTjHVfExtaqTtNSpXYck

