# lablab submission fields — paste-ready

Fill the `<<...>>` placeholders at hour ~22 from the real numbers. Everything else is final text.
Submit at hour 23 even if numbers are provisional; edit afterwards.

---

## Project title — HARD LIMIT 50 CHARACTERS

`ReviewReady — your repo's rules as IBM Bob modes`  (48 chars, in `field-title.txt`)

The old 75-character title does not fit the form. The form's real limits, read off the live
wizard on 2026-09-27: title 5-50, short description 50-255, long description 500-4000,
IBM Bob Usage Statement 500-4000.

## Short description (lablab hard limit: 255 characters — this one is 248)

> IBM Bob compiles a repo's own CONTRIBUTING.md and PR template into an executable contract, then runs it as Bob custom modes against a pull request before you submit. On seven real PRs we did not write: caught 5 of 5 rejections, blocked 0 good ones.

(Longer framing — maintainers drowning in LLM-assisted PRs, rules already written down in prose that
nothing enforces, fails in ninety seconds instead of after fourteen silent days — goes in the long
description and on slide 2, not here.)

## Long description — 500-4000 characters

See `field-long-description.md` (3,955 chars). Paste it whole. The earlier
`long-description.md` was 4,485 characters and is deleted; it also had the four PRs' ages
wrong (14/16/15/17) and called them "contributor-days". Verified from the corpus, they are
**17, 14, 16 and 14 days open, 61 total**.

## IBM Bob Usage Statement — 500-4000 characters, REQUIRED

See `field-bob-usage.md` (3,819 chars). Paste it whole. This field was not in our original
plan; it is required and it is where the "clear application of IBM Bob" criterion is scored.

## Technology & category tags

`IBM Bob 2.0` · `IBM Bob` · `Agent mode` · `Subagents` · `Developer tools` · `Code review` ·
`Open source` · `Python` · `C++` · `GitHub`

(Confirm the exact tag vocabulary lablab offers; always pick the IBM Bob 2.0 tag first.)

## Cover image

1280×720. Left: a wall of grey closed-PR rows with "closed after 14 days, unreviewed" repeated.
Right: one green READY stamp. Title lockup bottom-left, "Built with IBM Bob 2.0" bottom-right.
Source file in `assets/cover.html`, exported to PNG.

## Video presentation — BUILT

`writeup/reviewready.mp4` · 1920×1080 · **2:16** · 2.5 MB · H.264. **Captioned, no voice-over** (user's
choice). Regenerate with `python3 writeup/build_video.py`.

It does **not** show Bob producing the work, because the Bobcoins ran out before any session was
recorded and no session screenshots exist. It shows the artefact instead: the four closed PRs, the two
existing CI gates, the CONTRIBUTING sentence beside the rule Bob compiled from it, the inferred
`llm-disclosure` rule, the three checkers running on #1794 with real output, the #1797 miss, the results,
and the live demo. **Still needs a human:** upload it (YouTube unlisted or lablab's own upload) and
verify it plays in a logged-out private window.

### Original plan, superseded

**2:00 target, 2:15 hard cap** — May's 1:50 and 1:36 videos took 2nd and 3rd against a five-minute allowance (lablab's stated maximum is 5:00, **MP4**). Storyboard in `video-storyboard.md`. Keep the MP4 master; upload unlisted to YouTube; **verify it plays in a
logged-out private window** before pasting the link.

## Slide presentation

**8 slides**, outline in `slides-outline.md`. lablab requires the deck as a **PDF** — export it, do not link a Keynote/Slides URL.

## Demo application platform + URL — LIVE

**https://cvasilopoulos.github.io/reviewready/** — GitHub Pages, served from `docs/` on `master`,
built by `scripts/build_demo.py` from the report JSON. All ten pull requests, 306 findings, the contract
rule and source line behind each one, and what really happened to that PR. No backend, so it cannot
break during judging. Verified live: HTTP 200, interactive, responsive at phone width.

If the form's platform dropdown offers only Streamlit / Replit / Vercel, pick **Other** and paste this
URL; if it will not accept it, Vercel can import the same repo and serve `docs/` with no build step.

### Original plan, superseded

lablab's guidelines name Streamlit, Replit or Vercel as the platform choices, so the form's dropdown may
not offer GitHub Pages. Plan A: **Vercel** — import the public repo in the Vercel web UI (user action, no
CLI: local Node is broken) and serve the static `docs/` folder; Plan B: GitHub Pages under "Other" if the
form allows it. Either way the URL is the rendered report with the corpus results preloaded, so it needs
no backend and cannot break during judging. **Open it in a logged-out private window before pasting.**

## Code repository

`https://github.com/<user>/reviewready` — public, MIT, containing:

- `contract.yml` and the five checkers (Bob-authored)
- `bob_sessions/` — **the four Bob sessions exported from IBM Bob's own local database** by
  `scripts/export_bob_sessions.py`: task id, exact prompt, Bobcoin spend and context breakdown, and
  every tool call with its timestamp. Plus `ATTRIBUTION.md`, Bob's own per-file edit log, and
  `LEDGER.md`. Totals 39.79 of 40 Bobcoins, matching the IDE's 0% remaining.
  **There are still no screenshots** — none was ever captured, and `PROVENANCE.md` says so. The
  export is offered in their place and is strictly more checkable.
- `corpus/` — the cached labelled PR corpus
- `reports/` — per-PR gate reports and `SUMMARY.md`
- `PROVENANCE.md` — exactly which files Bob authored
- `LICENSE` (MIT)
