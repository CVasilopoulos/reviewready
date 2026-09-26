**In one sentence:**
This lets anyone on Windows actually run the spiral fitter, which today stops with an error before its first optimizer iteration.

**One real example:** 
Starting with a scroll spiral dataset on Windows 11, I ran fit_spiral.py, and it loaded the whole dataset, printed the first PROGRESS line, then died with ValueError: high is out of bounds for int32. With this change the same command keeps optimizing.

**Before:** 
The run loads tracks, lasagna fields and the shell table, prints "PROGRESS Optimizing 0/30,000 iterations", then raises ValueError: high is out of bounds for int32 from losses.py in _sample_patch_points. It is not an edge case: prefetch_enabled() returns False unless FIT_SPIRAL_PREFETCH=1 is set, so this is the path a Windows user gets by default.
 The fitter cannot start at all.

**After this PR:**
The same command starts optimizing and keeps running.

**Proof:** 
Two lines in a fresh python session on Windows reproduce the failure with no data and no checkout at all:

    import numpy as np
    np.random.randint(0, np.iinfo(np.int64).max)
    ValueError: high is out of bounds for int32

What to look at is the bound. RandomState.randint defaults to the C long, which is 32 bits on Windows and 64 bits on Linux, and losses.py asks for a 64-bit seed with seed = int(rng.randint(0, np.iinfo(np.int64).max)). The identical call succeeds on Linux, which is why this has been invisible.

Same settings, before and after, for the part that matters to reviewers, that existing sampling is untouched :

    np.random.seed(12345); [np.random.randint(0, 1000) for _ in range(5)]
    before: [482, 485, 285, 129, 420]
    after:  [482, 485, 285, 129, 420]

A bound of exactly np.iinfo(np.int32).max also gives the same value before and after. int64 is only requested when the bound does not fit in int32, so every existing small-range call keeps the historical bit stream, which is the stated purpose of LegacyNumpyRandom.

**Why / where this is useful:**
Anyone who tries the spiral fitter on Windows. Right now they hit this in the first second of optimization, after a long dataset load, with an error that points at numpy rather than at the cause.
With the fix they can run fits and report real results instead of a portability bug.

- [x] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

Tested on Windows 11, Python 3.14.2, NumPy 2.5.2, villa at commit de139a6, before spiral-fitting moved to the repo root.
The dataset was a scoll spiral root with tracks, lasagna normals and grad_mag, a measured outer shell and four patches.

Call chain of the failure:

    fit_spiral.py in step
    losses.py in get_patch_and_umbilicus_losses
    losses.py in _sample_patch_batch      return build(prefetch.LegacyNumpyRandom)
    losses.py in build
    losses.py in _sample_patch_points     seed = int(rng.randint(0, np.iinfo(np.int64).max))
    numpy/random/mtrand.pyx in RandomState.randint
    ValueError: high is out of bounds for int32

The traceback above is shortened to the call chain, with only the two source lines that matter kept.

Why the fix goes in LegacyNumpyRandom and not in losses.py: the prefetch path passes a _GeneratorShim, which delegates to Generator.integers and already defaults to int64, and that shim takes no dtype argument. Patching the call site would therefore break the other path. losses.py also uses LegacyNumpyRandom unconditionally in _sample_requested_patch_rows, so a call-site patch would need to be repeated there.

The same latent pitfall exists in StepPrefetcher.np_rng, which calls np.random.randint(0, 2 ** 63 - 1) without a dtype. That would raise on Windows for anyone who sets FIT_SPIRAL_PREFETCH=1. This PR fixes it too.

Limitations : I have only tested this on Windows and I have not run the full fit to completion on Linux, so I cannot claim a before and after comparison of final results. The argument that results are unchanged rests on the bit stream check above rather than on a completed run.

Tooling note : I used an LLM assistant (Claude Opus 5) while tracking this down. The crash, the diagnosis and the reproduction are from my own machine, running the spiral fitter on a real dataset.

cc @nvining

