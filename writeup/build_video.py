#!/usr/bin/env python3
import html
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SEED = HERE.parent / "gate-seed"
WORK = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "_video")
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
W, H = 1920, 1080

CSS = """
:root{--bg:#0b0f17;--bg2:#0d121b;--fg:#e8eef9;--dim:#8d97a8;--faint:#6b7686;--line:#232b39;
      --accent:#3ba3ff;--good:#2ecc71;--bad:#e2685f;--warn:#e0a33e}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden}
body{background:linear-gradient(160deg,#0b0f17,#131a26);color:var(--fg);
     font:26px/1.5 "Inter",-apple-system,BlinkMacSystemFont,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.brand{position:absolute;top:44px;left:72px;font-size:19px;letter-spacing:.17em;text-transform:uppercase;
       color:#46505f}
.stage{position:absolute;top:118px;left:72px;right:72px;bottom:268px;display:flex;flex-direction:column;
       justify-content:center;gap:26px}
.kicker{font-size:20px;letter-spacing:.17em;text-transform:uppercase;color:var(--faint)}
h1{font-size:82px;line-height:1.04;letter-spacing:-.03em;font-weight:680}
h1 span{color:var(--accent)}
h2{font-size:50px;line-height:1.1;letter-spacing:-.02em;font-weight:650}
h2 em{font-style:normal;color:var(--accent)}
.capbar{position:absolute;left:0;right:0;bottom:0;height:252px;background:#070a10;
        border-top:1px solid var(--line);padding:42px 72px 0}
.cap{font-size:40px;line-height:1.34;font-weight:500;letter-spacing:-.012em;max-width:1640px}
.cap b{color:var(--accent);font-weight:600}
.cap i{font-style:normal;color:var(--good)}
.cap s{text-decoration:none;color:var(--bad)}
.prog{position:absolute;left:0;bottom:0;height:5px;background:var(--accent)}
.card{background:#0d121b;border:1px solid var(--line);border-radius:16px;padding:30px 34px}
.card h3{font-size:19px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);
         font-weight:600;margin-bottom:20px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:38px;align-items:stretch}
table{width:100%;border-collapse:collapse;font-size:29px}
th{text-align:left;font-size:17px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint);
   font-weight:600;padding:0 20px 16px 0;border-bottom:1px solid var(--line)}
td{padding:20px 20px 20px 0;border-bottom:1px solid #1a212c;color:#c3cddb}
td.n{font-family:ui-monospace,monospace;color:var(--dim);width:150px}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;font-size:22px;padding:5px 17px;border-radius:99px;border:1px solid;white-space:nowrap}
.pill.bad{color:#d98077;border-color:#3d2326;background:#2a1a1c}
.pill.good{color:var(--good);border-color:#1e402c;background:#132318}
.pill.warn{color:var(--warn);border-color:#413318;background:#241d10}
pre{font-size:25px;line-height:1.62;color:#a9b6c9;white-space:pre-wrap}
pre .k{color:var(--accent)} pre .c{color:#5c6675} pre .g{color:var(--good)} pre .r{color:var(--bad)}
.q{border-left:5px solid #2a3442;padding-left:26px;color:var(--dim);font-size:31px;line-height:1.48;font-style:italic}
.q b{color:#cbd5e2;font-style:normal;font-weight:500}
.src{font-family:ui-monospace,monospace;font-size:19px;color:#4e5768;margin-top:12px;font-style:normal}
.term{background:#05070b;border:1px solid var(--line);border-radius:14px;padding:26px 30px;height:100%;
      overflow:hidden}
.term pre{font-size:22px;line-height:1.5;color:#9fb0c4}
.term .p{color:var(--good)}
.metric{display:flex;gap:74px}
.metric div b{display:block;font-size:76px;letter-spacing:-.025em;line-height:1.05;font-weight:680}
.metric div small{font-size:19px;letter-spacing:.11em;text-transform:uppercase;color:var(--faint)}
.big{font-size:120px;font-weight:700;letter-spacing:-.04em;line-height:1}
.big span{color:var(--accent)}
.foot{font-size:24px;color:var(--faint);line-height:1.45}
.foot b{color:var(--dim);font-weight:600}
.url{font-size:44px;font-weight:620;letter-spacing:-.01em}
"""


def esc(s):
    return html.escape(str(s))


def frame(stage, caption, pct):
    return f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="brand">ReviewReady · built with IBM Bob 2.0</div>
<div class="stage">{stage}</div>
<div class="capbar"><div class="cap">{caption}</div></div>
<div class="prog" style="width:{pct:.2f}%"></div>"""


PR_ROWS = [
    ("#1391", "Fix vc_obj2tifxyz TIFXYZ scale semantics", "17 days"),
    ("#1412", "test_command_line_tool_runner: abort the test slot", "14 days"),
    ("#1630", "vc_obj2tifxyz: fail instead of writing sentinels", "16 days"),
    ("#1724", "tifxyz_label_transfer: close memory maps", "14 days"),
]

TERM_LINES = [
    ('<span class="p">$</span> python3 scripts/check_prior_art.py --pr 1794', 0),
    ("", 0),
    ('  <span style="color:#e2685f">blocker</span>  prior-art/closed-pr-same-issue', 0),
    ('    PR #1630 references the same issue(s): #1320', 0),
    ('    shared files: volume-cartographer/apps/src/vc_obj2tifxyz.cpp', 0),
    ('    state=CLOSED  mergedAt=None  closer=bot', 0),
    ("", 0),
    ('  <span style="color:#e2685f">blocker</span>  prior-art/open-pr-same-issue', 0),
    ('    PR #1781 references the same issue(s): #1320', 0),
    ('    shared files: volume-cartographer/apps/src/vc_obj2tifxyz.cpp', 0),
    ("", 0),
    ('<span class="p">$</span> python3 scripts/check_contract.py --pr 1794', 0),
    ('  <span style="color:#e2685f">blocker</span>  real-scroll-data-origin', 0),
    ('  <span style="color:#e0a33e">major</span>    pr-verification-checkbox', 0),
    ("", 0),
    ('<span class="p">$</span> python3 scripts/check_evidence.py --pr 1794', 0),
    ('  <span style="color:#e2685f">blocker</span>  evidence/no-before-commit', 0),
    ("", 0),
    ('  verdict: <span style="color:#e2685f">BLOCK</span>   0.42s', 0),
]


def shots():
    s = []

    s.append((7.0, [(
        """<div class="kicker">IBM Bob 2.0 Hackathon · September 2026</div>
        <h1>Your repo's contribution rules,<br><span>compiled into an agentic gate.</span></h1>
        <div class="foot" style="font-size:28px;margin-top:8px">Target repository <b>ScrollPrize/villa</b>
          · evaluated on ten real pull requests</div>""",
        "<b>ReviewReady.</b> No voice-over — captions only.")]))

    rows = "".join(
        f'<tr><td class="n">{n}</td><td>{esc(t)}</td><td>{d}</td>'
        f'<td><span class="pill bad">closed unreviewed</span></td></tr>'
        for n, t, d in PR_ROWS)
    s.append((11.0, [(
        f"""<h2>Four working fixes. <em>Sixty-one days open.</em></h2>
        <table><tr><th>PR</th><th>What it fixed</th><th>Open for</th><th>Outcome</th></tr>{rows}</table>""",
        "These four pull requests fix real bugs. They waited seventeen, fourteen, sixteen and fourteen days. "
        "Then a bot closed them. <b>Nobody read them.</b>")]))

    s.append((7.0, [(
        f"""<h2>Four working fixes. <em>Sixty-one days open.</em></h2>
        <table><tr><th>PR</th><th>What it fixed</th><th>Open for</th><th>Outcome</th></tr>{rows}</table>""",
        "Two of the four were later fixed all over again, from scratch, by <b>other people</b>.")]))

    s.append((11.0, [(
        """<h2>The repo already runs two gates.</h2>
        <div class="cols">
          <div class="card"><h3>pr-time-limits.yml</h3>
            <pre><span class="c">inactive_cutoff=$(date -u -d</span> <span class="k">'14 days ago'</span><span class="c">)</span>
  ...
  <span class="r">gh pr close "$number"</span></pre></div>
          <div class="card"><h3>large-pr-review-gate.yml</h3>
            <pre><span class="k">LARGE_PR_FILE_THRESHOLD</span>: <span class="k">"20"</span>
<span class="c">// block large PRs unless approved</span></pre></div>
        </div>""",
        "The maintainers already automated what they could. <b>One counts days. One counts files.</b>")]))

    s.append((10.0, [(
        """<h2>But the rules that decide a pull request <em>are prose.</em></h2>
        <div class="card"><div class="q">“Any bugfix PR must be accompanied by a screenshot of the error …
          and the script/tool running without error afterward”<div class="src">CONTRIBUTING.md:19</div></div></div>
        <div class="card"><div class="q">“reviewing PRs takes a significant amount of time away from the goal
          of unrolling the scrolls”<div class="src">CONTRIBUTING.md · AI Guidelines</div></div></div>""",
        "The rules that actually decide a pull request here are written in prose. <b>Nothing enforces prose.</b>")]))

    s.append((13.0, [(
        """<h2>IBM Bob read them and <em>compiled a contract.</em></h2>
        <div class="cols">
          <div class="card"><h3>CONTRIBUTING.md — what a human wrote</h3>
            <div class="q" style="font-size:27px">“Any bugfix PR must be accompanied by a screenshot of the
              error … and the script/tool running without error afterward”<div class="src">line 19</div></div></div>
          <div class="card"><h3>contract.yml — what Bob compiled</h3>
            <pre>- <span class="k">id</span>: bugfix-error-screenshot
  <span class="k">source</span>: CONTRIBUTING.md:19
  <span class="k">check</span>: (a) a screenshot or terminal
    block showing the error, <span class="g">and</span> (b) one
    showing the tool running after
  <span class="k">severity</span>: blocker</pre></div>
        </div>""",
        "So IBM Bob read them and compiled them into an executable contract. "
        "<b>Twenty-seven rules</b> — each citing the sentence it came from.")]))

    s.append((10.0, [(
        """<h2>And it did it <em>in parallel.</em></h2>
        <div class="card"><h3>Session 01 · subagents · from Bob's own database</h3>
        <table style="font-size:25px"><tr><th>started</th><th>Bobcoins</th><th>surveying</th></tr>
        <tr><td class="n">19:36:14</td><td>0.170218</td><td><code>vesuvius/</code></td></tr>
        <tr><td class="n">19:36:14</td><td>0.206261</td><td><code>volume-cartographer/</code></td></tr>
        <tr><td class="n">19:36:14</td><td>0.033637</td><td><code>ink-detection/</code>, <code>spiral-fitting/</code></td></tr>
        <tr><td class="n">19:37:05</td><td>0.140670</td><td><code>dinovol/</code> and the rest</td></tr>
        </table></div>
        <div class="foot">21 minutes, 3.69 Bobcoins for the whole session. Every call is logged in
          <code>bob_sessions/01</code>, exported from <code>~/.bob/db/bob.db</code>.</div>""",
        "Before compiling, Bob fanned out <b>four subagents</b> to survey villa's subprojects — "
        "three of them started in the same second.")]))

    s.append((12.0, [(
        """<h2>And it found <em>the rule nobody wrote down.</em></h2>
        <div class="card" style="border-color:#1d3a55;background:#0c1622">
          <pre>- <span class="k">id</span>: llm-disclosure
  <span class="k">source</span>: <span class="g">inferred</span>
  <span class="k">rationale</span>: CONTRIBUTING.md defines a rule-set for "LLM generated" PRs,
    but no disclosure mechanism is specified. Without disclosure
    the llm-* rules are unenforceable.</pre></div>
        <div class="foot">villa has <b>six rules</b> for LLM-assisted pull requests and <b>no rule that you must
          disclose using one</b>. Marked <code>inferred</code>, with a rationale instead of a quote, so a
          maintainer can reject it.</div>""",
        "Bob also found a hole: six rules for LLM-assisted PRs, and <b>no rule that you must disclose using one</b>.")]))

    term_frames = []
    steps = list(range(3, len(TERM_LINES) + 1, 2)) + [len(TERM_LINES)]
    for i, k in enumerate(steps):
        text = "\n".join(l for l, _ in TERM_LINES[:k])
        term_frames.append((
            f"""<h2>Three checkers. <em>Shipped as Bob custom modes.</em></h2>
            <div class="term"><pre>{text}</pre></div>""",
            "Three checkers ship as Bob custom modes, each with read, execute and todo — "
            "nothing that can write. Here they run on <b>#1794</b>."))
    s.append((15.0, term_frames))

    s.append((10.0, [(
        """<h2>It found the <em>duplicate</em> the repo's own CI cannot see.</h2>
        <div class="card"><pre>  <span class="r">blocker</span>  prior-art/closed-pr-same-issue
    PR #1630 references the same issue(s): #1320
    shared files: vc_obj2tifxyz.cpp
    state=CLOSED  mergedAt=None  closer=<span class="r">bot</span></pre></div>
        <div class="foot">#1794 was written because #1630 had been closed by the bot and was invisible.
          <b>Counting files and counting days cannot find that.</b></div>""",
        "#1794 exists because an earlier fix was bot-closed and invisible. "
        "<b>Neither existing gate catches either duplicate.</b>")]))

    s.append((13.0, [(
        """<h2>And here is one it <em>gets wrong.</em></h2>
        <div class="cols">
          <div class="card"><h3>What ReviewReady said</h3>
            <span class="pill warn">REVISE</span>
            <pre style="margin-top:18px"><span class="k">llm-concise-description</span>
  description too long</pre></div>
          <div class="card" style="border-color:#3d2326"><h3 style="color:#d98077">Why #1797 was really closed</h3>
            <div class="q" style="border-color:#4a2c2f;font-size:27px">“I see no good reason to add this
              mixture?”<div class="src">maintainer, 2026-09-22</div></div></div>
        </div>
        <div class="foot">Nothing in <code>CONTRIBUTING.md</code> says flags must compose into a coherent
          interface — so no rule can. That is a <b>fourth checker we never built</b>: the Bobcoins ran out
          at three.</div>""",
        "And here is one it gets wrong. <s>A miss.</s> The checker that would catch it "
        "was never built — the budget ran out at three.")]))

    s.append((12.0, [(
        """<h2>Measured on pull requests <em>we did not write.</em></h2>
        <div class="metric">
          <div><b style="color:var(--good)">5 / 5</b><small>hold-out recall</small></div>
          <div><b style="color:var(--good)">0 / 2</b><small>hold-out false blocks</small></div>
          <div><b>6 / 7</b><small>whole corpus recall</small></div>
          <div><b style="color:var(--warn)">1</b><small>false block</small></div>
        </div>
        <div class="foot" style="font-size:27px">Tuned on our own pull requests, evaluated on other people's.
          <b>Every row is a public PR you can open.</b> The one false positive is named in the table, not
          hidden in the notes.</div>""",
        "On the seven pull requests we did not write: <i>five of five caught, zero good ones blocked.</i>")]))

    s.append((11.0, [(
        """<div class="kicker">Everything is public</div>
        <h1 style="font-size:64px">Open the gate's report<br><span>for any of the ten.</span></h1>
        <div class="card"><div class="foot" style="font-size:27px">
          <b>cvasilopoulos.github.io/reviewready</b> — every finding, the contract rule behind it,
          and what really happened to that pull request.</div></div>
        <div class="url">github.com/CVasilopoulos/reviewready</div>
        <div class="foot">MIT · <code>PROVENANCE.md</code> states file by file what Bob produced and what it
          did not. Built with IBM Bob 2.0. AI-assisted, human-directed.</div>""",
        "Everything is public — the contract, the modes, the corpus, and the two results we got wrong.")]))

    return s


def render(shot_list):
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    total = sum(d for d, _ in shot_list)
    entries, elapsed, idx = [], 0.0, 0
    for dur, frames in shot_list:
        per = dur / len(frames)
        for stage, cap in frames:
            pct = 100.0 * elapsed / total
            src = WORK / f"f{idx:03d}.html"
            png = WORK / f"f{idx:03d}.png"
            src.write_text(frame(stage, cap, pct))
            subprocess.run(
                [BRAVE, "--headless", "--disable-gpu", "--no-sandbox",
                 f"--window-size={W},{H}", "--virtual-time-budget=2500",
                 f"--screenshot={png}", f"file://{src}"],
                capture_output=True, check=True)
            if not png.exists():
                raise SystemExit(f"frame {idx} did not render")
            entries.append((png, per))
            elapsed += per
            idx += 1
    return entries, total


def encode(entries, total, out):
    lst = WORK / "concat.txt"
    with lst.open("w") as f:
        for png, dur in entries:
            f.write(f"file '{png.name}'\nduration {dur:.4f}\n")
        f.write(f"file '{entries[-1][0].name}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-t", f"{total:.3f}",
         "-vf", f"fps=25,scale={W}:{H}:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart",
         str(out)], check=True, cwd=WORK)
    return out


def main():
    out = HERE / "reviewready.mp4"
    sl = shots()
    entries, total = render(sl)
    encode(entries, total, out)
    mb = out.stat().st_size / 1e6
    print(f"{out.name}: {len(entries)} frames, {total:.0f}s target, {mb:.1f} MB")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
         "-of", "default=nw=1", str(out)], capture_output=True, text=True)
    print(probe.stdout.strip())


if __name__ == "__main__":
    main()
