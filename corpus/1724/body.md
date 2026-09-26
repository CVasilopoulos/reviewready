**Motivation (written by me, not the assistant):** I am running this codebase on Windows to work on ink detection, and tifxyz_label_transfer fails there in a way it does not on Linux, because the memory maps are never closed. It cost me time working out that the failures were the tool's and not my environment's.

**In one sentence:** `load_surface`, `read_image`, `load_tifxyz_mask` and the new `read_render_array` no longer leave files memory-mapped, and `TemporaryRaster.close` releases its own mapping, so on Windows a directory a reader touched can be deleted afterwards and the module's test suite passes; `read_render_tiff` keeps its documented mapping contract.

**One real example:** Starting with the published segment `PHercParis4/segments/20231106155351/mesh/20231106155351-on-20260411134726-2.4um.tifxyz` (52.7 MB, anonymous S3 read), I ran `load_surface` + `read_image` on a fresh `TemporaryDirectory` copy and deleted that copy while the returned arrays were still live: on `main` (23adee0) the delete fails with `WinError 32` in 10 of 10 runs; on this branch (aa38d7a) it succeeds in 10 of 10, for +16.7 MiB resident and +4 ms at the median.

**Before:** `python -m pytest tests/tifxyz_label_transfer -q` on Windows: 8 failed / 121 passed / 5 skipped, every failure a `PermissionError: [WinError 32]` raised by temp-dir cleanup, not by a test body.

**After this PR:** 132 passed / 5 skipped. Readers hand out owned arrays (`read_render_array`) or close their mapping (`TemporaryRaster.close`, `io.close_memmap`); `read_render_tiff` keeps its documented mapping contract and its test.

**Proof:** `python -m pytest tests/tifxyz_label_transfer -q` on Windows 11, run today against
current `main` (b218ace) and against this branch (aa38d7a) from the same installed checkout:

![before: 8 failed on main](https://gist.githubusercontent.com/hunghy93-pixel/c7c08ffda4b6a592660976f65884a5a9/raw/before_1671.png)

![after: 132 passed on this branch](https://gist.githubusercontent.com/hunghy93-pixel/c7c08ffda4b6a592660976f65884a5a9/raw/after_1671.png)

Raw output for both runs is in the same gist ([before](https://gist.githubusercontent.com/hunghy93-pixel/c7c08ffda4b6a592660976f65884a5a9/raw/before_1671.txt), [after](https://gist.githubusercontent.com/hunghy93-pixel/c7c08ffda4b6a592660976f65884a5a9/raw/after_1671.txt)); each of the eight failures on `main` carries `WinError 32`.

**Why / where this is useful:** anyone running `tifxyz_label_transfer` or its tests on Windows (CI is `ubuntu-latest` only, so it never showed there), and Windows callers can release temporary files after these reads.

- [x] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

On Windows, `tests/tifxyz_label_transfer/` fails 8 tests with `PermissionError:
[WinError 32]` from `tempfile.TemporaryDirectory` cleanup, not from any test body.

**Root cause.** The module hands callers live memory mappings with no way to release
them. `io._read_tiff` returned `tifffile.memmap(...)`, so `load_surface`, `read_image`
and `load_tifxyz_mask` returned arrays whose `.base` chain still mapped `x.tif`, and
`view_alignment_napari.read_render_tiff` did the same for every cached render.
`io.TemporaryRaster.close()` released its mapping only via `del self.array`, which is
not enough when a caller holds the array it was given — and `core.py` documents that
callers may. POSIX allows unlinking a mapped file, so none of this shows on Linux, and
CI is `ubuntu-latest` only.

**Fix.** `io.close_memmap()` is the explicit end of life these mappings lacked.
`TemporaryRaster.close()` closes its mapping before unlinking (the issue's option 1: it
owns the file, and every read happens before its `ExitStack` unwinds). `_read_tiff` and
the eight `read_render_tiff` call sites that hand a render to a caller return owned
arrays instead, the latter through a new `read_render_array()` (option 2);
`read_render_tiff` keeps its documented mapping contract and its test. `close_memmap`
refuses a view, because NumPy copies `_mmap` onto every view and closing through one
frees the parent's pages under everyone else — a segfault here, not an exception
(CPython 3.14.7, NumPy 2.5.2), which is why the reader paths cannot simply close.

**Memory trade-off.** `read_render_array` returns an in-RAM copy where the
uncompressed-TIFF branch returned a mapping — one render per call. The largest call
site is `load_middle_three_max`, whose level-2 composites exceed 200 MiB (documented at
`prepare_canvas_offset_evidence.py:420-422`), and `prepare_case` can hold four renders
live at `--preview-factor 1`. Measured on **synthetic** data (8000x8000 uint8
uncompressed TIFF, 61 MiB; Windows 11, Python 3.14.7, RSS via psutil; reproduce with
`bench_render_read.py`, in the gist https://gist.github.com/hunghy93-pixel/c7c08ffda4b6a592660976f65884a5a9):

```
read_render_tiff, untouched    0.006 s   +0 MiB RSS   temp dir NOT removable (WinError 32)
read_render_tiff, then .sum()  0.060 s  +61 MiB RSS   temp dir NOT removable (WinError 32)
read_render_array              0.055 s  +61 MiB RSS   temp dir removable immediately
```

In this synthetic benchmark the fully touched mapping and the copy both added about 61 MiB RSS,
but the copy changes what that memory is: evictable page cache on `main`, anonymous RAM on this branch — the
same trade `_read_tiff` now makes (see its docstring). In the napari viewer that is up to four
level-2 composites (>200 MiB each, `prepare_canvas_offset_evidence.py:420-422`) at
`--preview-factor 1`, not measured here on a real composite. If you would rather keep the viewer
mapped, the alternative is `close_memmap` at case release instead of `read_render_array` at read
time; I took the copy because no call site reads a render lazily, and switching is a small
follow-up. The subpackage's three other `tifffile.memmap` sites (`prepare_canvas_offset_evidence.py:423`,
`:637`, `self_render_tifxyz.py:959-969`) are function-local or unlink before mapping and
are untouched; `vesuvius/tifxyz/reader.py:353` is outside this subpackage and out of scope.

**Real-data receipt.** Repeated on a published segment rather than a synthetic raster:
`PHercParis4/segments/20231106155351/mesh/20231106155351-on-20260411134726-2.4um.tifxyz`
from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/` (anonymous read,
no account) — `x/y/z.tif` 17,575,454 B each plus `meta.json`, 52,726,772 B in all, float32
1715x2562 grids. Each reader runs against a fresh `TemporaryDirectory` copy, and that copy
is deleted while the returned arrays are still live; **ten runs per revision**,
`receipt_1671.py --repeat 10 --src <villa>/vesuvius/src/vesuvius/tifxyz_label_transfer --segment <downloaded segment dir>`, same gist (median / p95 over the ten):

```
                         main (23adee0)                 this branch (aa38d7a)
load_surface+read_image  NOT removable, WinError 32     removable
                         +54.5 MiB RSS                  +71.2 MiB RSS
                         0.072 s med / 0.116 s p95      0.076 s med / 0.092 s p95
read_render_tiff         NOT removable, WinError 32     NOT removable, WinError 32
                         +0.0 MiB RSS                   +0.0 MiB RSS
                         0.008 s med / 0.012 s p95      0.008 s med / 0.009 s p95
read_render_array        (does not exist)               removable
                                                        +16.8 MiB RSS
                                                        0.022 s med / 0.026 s p95
```

So on a real surface the branch costs one extra resident grid — +16.7 MiB, the `read_image`
copy that no longer aliases the already-mapped `x.tif` — for +4 ms at the median on that read
path (0.072 s → 0.076 s). The branch p95 was lower (0.092 s vs 0.116 s on `main`); ten runs do not establish a timing
regression either way. In exchange, the directory the reader touched becomes deletable.
`read_render_tiff` still maps, by contract.

```
python -m pytest tests/tifxyz_label_transfer -q
before: 8 failed, 121 passed, 5 skipped
after:  132 passed, 5 skipped
```

Windows 11, Python 3.14.7, tifffile 2026.6.1, test counts on NumPy 2.5.2 (2026-09-05), the real-data receipt on NumPy 2.4.6 (2026-09-06); `tests/test_surface_preflight.py`
(the only other importer) is unaffected: 16 passed. Of the three added tests only
`test_readers_and_temporary_rasters_leave_no_file_mapped` is a regression test — it walks
the `.base` chain rather than the platform's unlink behaviour, Linux regression behaviour has not been tested; the other two are unit tests of the new API and cannot run against `main`.

Measured against `main` at 23adee0 (2026-09-05). `main` has moved on since, to b218ace, but only
through website commits: nothing under `vesuvius/src/` changed, and this branch still merges
cleanly, so the comparison above stands as written.

Fixes #1671

