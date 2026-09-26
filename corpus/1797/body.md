**In one sentence:** After one remote render, you can rerun `vc_render_tifxyz` with the same `-v` directory and leave out `--remote-url`, as its help text already said.

**One real example:** I took a 30 x 30 cell window of PHercParis4 segment `20231007101619` and the published PHercParis4 45.532um volume on S3. I rendered once with `-v <dir> --remote-url <url>`, then again with only `-v <dir>`. The second run read the shared remote cache and wrote a byte-identical `00.tif`.

**Before:** The first render works but never creates `<dir>`. The second render exits 1 with `Error opening local zarr`, because nothing writes `<dir>/.remote_source.json`. `--remote-url` can never be omitted, and `-v` cannot stand in for it on the remote path.

**After this PR:** The first render writes `<dir>/.remote_source.json` with the URL. The second render picks it up, exits 0 and produces the same image from the persisted chunks.

**Proof:** Upstream main `d9d70bef1` against this branch on the same base, with the same segment window, volume and flags. The two renders of each build share one fresh `HOME`. The shared remote cache starts empty for render 1, and render 2 can use what render 1 fetched.

The attached images show the terminal output of these runs, rendered from the evidence script's log. Look at step 2 first: main exits 1 with `Error opening local zarr`, and this branch exits 0 after `Detected cached remote source`. In the blocks below, output is trimmed to the relevant lines. Lines starting with `#` are my notes on exit codes and files, not program output.

<img width="3624" height="1280" alt="1555-before-main" src="https://github.com/user-attachments/assets/7a221ac4-0844-4040-a870-8442e6cad519" />

<img width="3624" height="1424" alt="1555-after-fix" src="https://github.com/user-attachments/assets/43208833-d2dc-45aa-b707-fc1faa25b1d9" />

`<flags>` is `-s <segment> --scale 1 -g 0 -n 1 --cache-gb 2 --voxel-size 45.532 --tif-output <out>`.

1. First render, with `--remote-url`

Before (main):
```
$ vc_render_tifxyz -v <dir> --remote-url <url> <flags>
# exit 0, 600x600 render, <dir> is never created, 146 chunk files in the shared remote cache
```
After (this PR):
```
$ vc_render_tifxyz -v <dir> --remote-url <url> <flags>
Recorded remote source in <dir>/.remote_source.json
# exit 0, <dir> holds only .remote_source.json with the URL, 146 chunk files in the shared remote cache
```

2. Second render, same `-v`, no `--remote-url`

Before (main):
```
$ vc_render_tifxyz -v <dir> <flags>
Error opening local zarr: filesystem error: directory iterator cannot open directory: No such file or directory [<dir>]
# exit 1
```
After (this PR):
```
$ vc_render_tifxyz -v <dir> <flags>
Detected cached remote source: <url>
# exit 0
```

3. Output images

```
# this PR, render 2 (no --remote-url): 00.tif sha256 03206176091dcf30...
# this PR, render 1 (--remote-url):    00.tif sha256 03206176091dcf30...
# main, render 1 (--remote-url):       00.tif sha256 03206176091dcf30...
# 600x600 uint8, 83.5% nonzero, mean 74.7 (papyrus texture, not an empty render)
```
In the attached run, render 2 took 15 s and render 1 took 45 s cold. Cold times depend on S3, so this is not a speed-up from this patch. Main already persists chunks when `--remote-url` is given. The point is that the run without `--remote-url` now works and reads that cache.

4. VC3D-style call, where VC3D passes the URL as both `--volume` and `--remote-url`

```
$ cd <empty dir>
$ vc_render_tifxyz -v <url> --remote-url <url> <flags>
# main:    exit 0, 0 entries created in the working directory
# this PR: exit 0, 0 entries created in the working directory
```

5. `-v` already holds a local zarr

Before (main):
```
$ vc_render_tifxyz -v <zarrdir> --remote-url <url> <flags>
# nothing written, <zarrdir> holds only .zgroup
```
After (this PR):
```
$ vc_render_tifxyz -v <zarrdir> --remote-url <url> <flags>
Warning: <zarrdir> holds a local zarr; not recording the remote source
# nothing written, <zarrdir> still holds only .zgroup
```

**Why / where this is useful:**

I picked this up because the `--remote-url` help says the flag can be left out after the first render, and that never worked. I ran both renders on the published PHercParis4 volume from S3 and checked that the second run without `--remote-url` now works and writes the same image as the first.

After one render with `--remote-url`, reruns on the same volume only need `-v`. The `--remote-url` help is accurate again for URLs without a query string, which is what #1555 reported. VC3D renders behave the same as before.

- [x] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

### History

- #781 (`e81cf1420`, 2026-03-06) added `loadCachedRemoteUrl()`, a writer and the "(optional if --volume cache already records it)" wording.
- #844 (`557766a1b`, 2026-05-03) removed the writer together with the staged cache (`volume-cartographer/core/src/cache/HttpMetadataFetcher.cpp`). The reader stayed.
- #1657 (`38c2b4278`, merged 2026-09-14) carried the commits of #1656. Remote renders now open through `Volume::NewFromUrl` and use the shared persistent remote cache (default `$HOME/.VC3D/remote_cache`, or `remote_cache_dir` under `[viewer]` in `VC3D.ini`). It kept the wording. #1656 itself merged as an empty commit (`bfef6abe0`).
- @Bullo27 filed #1555 and asked whether to delete the reader or add the writer. In #1656's review he noted that `.remote_source.json` was only ever read, never written, and proposed writing it. @hendrikschilling asked to use the existing remote-volume cache infrastructure instead of another cache location.

This PR takes the writer option on top of that infrastructure, following @Bullo27's proposal. The marker holds only the URL. Chunks stay in the shared remote cache, and nothing is cached under `-v`. Auth is not stored. It still comes from the environment (`vc::HttpAuth::from_env()`) on every run.

### What changed

One file: `volume-cartographer/apps/src/vc_render_tifxyz.cpp`.

- `saveRemoteSourceMarker(vol_path, remoteUrl)` runs right after the remote volume opens and the requested level is found. It creates the directory, writes `{"url": ...}` with `utils::Json`, checks the stream after close and logs `Recorded remote source in <path>`.
- The `--remote-url` help now says fetched chunks persist under the shared remote cache root, not under `--volume`. It says the URL is recorded in `<volume>/.remote_source.json` once the remote volume opens (not when `--volume` is a URL or a local zarr), and that the flag can be omitted after that.
- The `-v` help now says that with `--remote-url` the directory can still supply the voxel size (`meta.json`/`metadata.json`), and that it records the remote source so later runs can omit `--remote-url`.
- Neither help string mentions the query-string case below. I can add it if you prefer.

### When it does not write

| Condition | Why |
|---|---|
| `--volume` contains `://` | VC3D passes the remote locator as both `--volume` and `--remote-url` (`volume-cartographer/apps/VC3D/SegmentationCommandHandler.cpp`, `volume-cartographer/apps/VC3D/CommandLineToolRunner.cpp`). Without this, the URL would be created as a relative directory tree in the working directory. |
| URL contains `?` | `volume-cartographer/docs/remote_file_cache.md` says the remote file cache removes query strings and fragments before persistence, because they may contain signed credentials. The marker is plain text, so it skips any URL with a query string. |
| Marker already holds the same URL | Repeat renders do not rewrite it. |
| `--volume` holds `.zgroup`, `.zarray`, `zarr.json` or `0` | The marker is read before the local path is chosen. A marker there would make a later run without `--remote-url` stream the remote volume instead of reading the local zarr. Logs a warning. |

Any failure to create the directory or write the file is logged as a warning. The render continues, because it does not depend on the marker.

The zarr check runs only when writing. If a local zarr is later copied into a directory that already has the marker, a run without `--remote-url` still streams the remote volume and logs `Detected cached remote source: <url>`. Removing `.remote_source.json` restores the local read.

### Tested

- Built and run on base `d9d70bef1`. The branch was then rebased onto `4b3c72882`, where `vc_render_tifxyz.cpp` is byte-identical. Cmake preset `ci-release-gcc`, in `ghcr.io/scrollprize/villa/volume-cartographer:builder-ubuntu-26.04`.
- Linux x86_64 only. Not tested on Windows or macOS.
- Segment: `PHercParis4/segments/20231007101619/mesh/20231007101619-on-20260310170716-45.532um.tifxyz`, cut to a 30 x 30 cell window. The window is the 30 x 30 block of the grid with the most valid points. It was copied out of `x.tif`, `y.tif` and `z.tif` into a new tifxyz folder, with `meta.json` copied and its `bbox` recomputed.
- Volume: `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr`
- Command: `vc_render_tifxyz -v <dir> [--remote-url <url>] -s <segment> --scale 1 -g 0 -n 1 --cache-gb 2 --voxel-size 45.532 --tif-output <out>`
- In the attached run, cold first renders took 30 s on main and 45 s on this branch, and the warm second render took 15 s. An earlier pair measured 70 s on main and 105 s on this branch, so the difference is S3 variance. The patch only adds a few file checks and one small file write.

### Open PRs that touch this

- #1763 (README) describes `-v` as a directory that "stays empty" and chunks as "cached in RAM only". Since #1657, chunks persist in the shared remote cache. With this PR, `-v` also gets `.remote_source.json`. That bullet may want an update. I can leave a note there.
- #1717 adds a post-render `EXIT_FAILURE` for surfaces outside the volume. A render that fails that check will still have recorded the URL, because the volume did open. That is why the help says "once the remote volume opens".
- #1681, #1695 and #1717 branch from before #1657, so a plain `git apply` of their old help-string context fails. A 3-way merge with this PR is clean in either order.

### Alternative

If you would rather not have the marker at all, the other option from #1555 is to delete the reader. That means removing `loadCachedRemoteUrl()`, its fallback in `main()`, the "or a cached remote source marker under --volume" part of the `--prefetch-remote` error and the parenthetical in the help. `--remote-url` would then be the only way to stream. That change is smaller and also fixes the misleading help. It also avoids a hidden file under `-v` that changes what a later run does. Happy to switch this PR to it.

AI-assisted (Claude Code), human-directed. All runs above were executed on real data, not inferred.
Fixes #1555

