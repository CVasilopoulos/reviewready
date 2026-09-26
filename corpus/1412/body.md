`expectSingleCompletion()` used QTest check macros inside a helper function; on failure they return from the helper only, so the test slot carried on into `completionSucceeded()`, which indexes an empty `QSignalSpy` — out of bounds, so the binary segfaulted instead of reporting a clean failure, taking the remaining tests with it (as observed in #1318).

The helper is now a macro, so a failed check returns from the calling test slot itself: the failure is reported cleanly and the rest of the suite still runs, with the same diagnostics as before.

## Verification

Built with `ghcr.io/scrollprize/vc3d-deps/linux:ubuntu-26.04`, run with `QT_QPA_PLATFORM=offscreen`, injecting a forced failure (a slot calling the helper with nothing started) into a scratch copy.

Before (helper as a function): FAIL! reported, then `Received signal 11 (SIGSEGV)` — the remaining tests never ran.

After (helper as a macro), same forced failure: clean FAIL!, all other tests still run (`Totals: 9 passed, 1 failed`), non-zero exit.

The unmodified suite passes: `Totals: 9 passed, 0 failed, 0 skipped, 0 blacklisted`.

Fixes #1318
