#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUT = ROOT / "docs" / "index.html"

HOLDOUT = {1391, 1412, 1630, 1683, 1724, 1794, 1595}
SEV_ORDER = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}


def ground_truth():
    rows = {}
    for line in (REPORTS / "SUMMARY.md").read_text().splitlines():
        m = re.match(r"\|\s*#(\d+)\s*\|(.*)\|\s*$", line.strip())
        if not m:
            continue
        c = [x.strip() for x in m.group(2).split("|")]
        if len(c) < 6:
            continue
        rows[int(m.group(1))] = {
            "verdict": c[0],
            "top": c[1].strip("`"),
            "outcome": c[2],
            "why": c[3],
            "agree": c[4].replace("*", "") == "yes",
            "incumbent": c[5],
        }
    return rows


def load():
    truth = ground_truth()
    out = []
    for p in sorted(REPORTS.glob("*.json"), key=lambda f: int(f.stem)):
        d = json.loads(p.read_text())
        n = d["pr"]
        d["truth"] = truth.get(n, {})
        d["holdout"] = n in HOLDOUT
        d["findings"].sort(key=lambda f: SEV_ORDER.get(f.get("severity", "nit"), 9))
        out.append(d)
    return out


HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReviewReady — the gate, on ten real pull requests</title>
<style>
:root{--bg:#0b0f17;--bg2:#0d121b;--fg:#e8eef9;--dim:#8d97a8;--faint:#6b7686;--line:#232b39;
      --accent:#3ba3ff;--good:#2ecc71;--bad:#e2685f;--warn:#e0a33e}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:15px/1.5 "Inter",-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
     -webkit-font-smoothing:antialiased}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--line);padding:22px 28px;display:flex;flex-wrap:wrap;
       gap:22px;align-items:flex-end;justify-content:space-between}
h1{font-size:20px;font-weight:650;letter-spacing:-.01em}
h1 span{color:var(--accent)}
.sub{font-size:13.5px;color:var(--dim);margin-top:5px;max-width:720px}
.metrics{display:flex;gap:26px}
.metrics div b{display:block;font-size:24px;line-height:1.1;font-weight:650}
.metrics div small{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint)}
.wrap{display:grid;grid-template-columns:330px 1fr;min-height:calc(100vh - 92px)}
.rail{border-right:1px solid var(--line);padding:16px 0;overflow-y:auto}
.railhead{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint);
          padding:0 20px 10px}
.pr{display:block;width:100%;text-align:left;background:none;border:0;border-left:3px solid transparent;
    padding:13px 20px;cursor:pointer;color:inherit;font:inherit}
.pr:hover{background:#101723}
.pr.on{background:#101723;border-left-color:var(--accent)}
.pr .r1{display:flex;align-items:center;gap:9px;margin-bottom:4px}
.pr .n{font-family:ui-monospace,monospace;font-size:13px;color:var(--dim)}
.pr .t{font-size:13.5px;color:#c3cddb;line-height:1.35;display:block}
.pr .r2{margin-top:6px;display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.tag{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);
     border:1px solid var(--line);border-radius:4px;padding:1px 6px}
.b{font-size:11px;padding:2px 9px;border-radius:99px;border:1px solid;white-space:nowrap;font-weight:500}
.b.BLOCK{color:#d98077;border-color:#3d2326;background:#2a1a1c}
.b.REVISE{color:var(--warn);border-color:#413318;background:#241d10}
.b.READY{color:var(--good);border-color:#1e402c;background:#132318}
.b.yes{color:var(--good);border-color:#1e402c;background:#132318}
.b.no{color:#d98077;border-color:#3d2326;background:#2a1a1c}
main{padding:26px 34px 60px;max-width:1080px}
.title{font-size:23px;font-weight:620;letter-spacing:-.015em;line-height:1.25}
.meta{font-size:13px;color:var(--dim);margin-top:8px}
.panel{background:var(--bg2);border:1px solid var(--line);border-radius:11px;padding:17px 19px;margin:20px 0}
.panel.truth{border-color:#1d3a55;background:#0c1622}
.panel h3{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint);
          margin-bottom:11px;font-weight:600}
.kv{display:grid;grid-template-columns:130px 1fr;gap:7px 16px;font-size:14px}
.kv dt{color:var(--faint);font-size:12.5px;padding-top:1px}
.kv dd{color:#c3cddb}
.f{border:1px solid var(--line);border-radius:10px;margin-bottom:11px;overflow:hidden}
.f>summary{list-style:none;cursor:pointer;padding:13px 16px;display:flex;gap:11px;align-items:baseline;
           background:var(--bg2)}
.f>summary::-webkit-details-marker{display:none}
.f>summary:hover{background:#101723}
.f .rid{font-family:ui-monospace,monospace;font-size:13.5px;color:var(--fg)}
.f .ck{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--faint)}
.f .conf{margin-left:auto;font-size:11.5px;color:var(--faint);font-family:ui-monospace,monospace}
.sev{font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:4px;
     border:1px solid;font-weight:600}
.sev.blocker{color:#d98077;border-color:#3d2326;background:#2a1a1c}
.sev.major{color:var(--warn);border-color:#413318;background:#241d10}
.sev.minor{color:#7f97b5;border-color:#243040;background:#131b26}
.sev.nit{color:#5b8f6d;border-color:#1c3326;background:#111c16}
.fbody{padding:4px 16px 16px;border-top:1px solid var(--line)}
.q{border-left:3px solid #2a3442;padding:2px 0 2px 13px;margin:12px 0;color:var(--dim);
   font-size:13.5px;line-height:1.5}
.src{font-family:ui-monospace,monospace;font-size:11.5px;color:#4e5768;margin-top:5px}
.ev{background:#0a0e15;border:1px solid #1a212c;border-radius:7px;padding:11px 13px;margin:9px 0;
    font-size:13px;color:#c3cddb}
.ev .where{font-family:ui-monospace,monospace;font-size:11.5px;color:var(--faint);margin-top:5px}
.ev pre{font-size:12px;color:#94a2b6;white-space:pre-wrap;margin-top:7px;line-height:1.5}
.fix{font-size:13.5px;color:#c3cddb;margin-top:11px}
.fix b{color:var(--accent);font-weight:500}
.filters{display:flex;gap:8px;margin:18px 0 14px;align-items:center;flex-wrap:wrap}
.filters button{background:var(--bg2);border:1px solid var(--line);color:var(--dim);border-radius:99px;
                padding:5px 13px;font:inherit;font-size:12.5px;cursor:pointer}
.filters button.on{border-color:var(--accent);color:var(--fg)}
.count{font-size:12.5px;color:var(--faint);margin-left:4px}
footer{border-top:1px solid var(--line);padding:20px 34px 34px;color:var(--faint);font-size:12.5px;
       line-height:1.6;max-width:1080px}
footer b{color:var(--dim);font-weight:600}
@media(max-width:820px){.wrap{grid-template-columns:1fr}.rail{border-right:0;border-bottom:1px solid var(--line)}
  header{padding:18px}main{padding:20px 18px 48px}footer{padding:18px}}
</style></head><body>
<header>
  <div>
    <h1>ReviewReady — <span>the gate, on ten real pull requests</span></h1>
    <div class="sub">Every verdict below was produced by running the three checker scripts over the cached
      corpus. Nothing is mocked. Pick a pull request to see what the gate said, the contract rule behind it,
      and what really happened to it.</div>
  </div>
  <div class="metrics">
    <div><b style="color:var(--good)">5 / 5</b><small>hold-out recall</small></div>
    <div><b style="color:var(--good)">0 / 2</b><small>hold-out false blocks</small></div>
    <div><b>27</b><small>contract rules</small></div>
    <div><b>3</b><small>Bob modes</small></div>
  </div>
</header>
<div class="wrap">
  <nav class="rail"><div class="railhead">ScrollPrize/villa · ten pull requests</div><div id="rail"></div></nav>
  <main id="main"></main>
</div>
<footer>
  <b>Hold-out</b> means the seven pull requests we did not write. The other three are ours, and the gate was
  tuned on them, so they are reported separately. <b>Two of the ten the gate gets wrong</b> — #1798 is a false
  positive on a clean pull request, #1797 is a miss that needed a fourth checker we never built. Both are shown
  here rather than hidden. <b>Built with IBM Bob 2.0.</b> AI-assisted, human-directed.
  <a href="https://github.com/CVasilopoulos/reviewready">github.com/CVasilopoulos/reviewready</a>
</footer>
<script>
const DATA = __DATA__;
let cur = DATA[0].pr, sev = "all";
const esc = s => String(s == null ? "" : s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const SEVS = ["blocker","major","minor","nit"];

function rail(){
  document.getElementById("rail").innerHTML = DATA.map(d => `
    <button class="pr ${d.pr===cur?"on":""}" data-pr="${d.pr}">
      <span class="r1"><span class="n">#${d.pr}</span><span class="b ${d.truth.verdict}">${d.truth.verdict}</span></span>
      <span class="t">${esc(d.title)}</span>
      <span class="r2">
        <span class="tag">${d.holdout?"hold-out":"ours"}</span>
        <span class="tag">${esc(d.truth.outcome||d.state)}</span>
        <span class="b ${d.truth.agree?"yes":"no"}">${d.truth.agree?"agrees":"wrong"}</span>
      </span>
    </button>`).join("");
  document.querySelectorAll(".pr").forEach(b =>
    b.onclick = () => { cur = +b.dataset.pr; rail(); body(); window.scrollTo({top:0,behavior:"smooth"}); });
}

function finding(f){
  const r = f.rule || {};
  const ev = (f.evidence||[]).map(e => `
    <div class="ev">${esc(e.what)}
      ${e.where?`<div class="where">${esc(e.where)}</div>`:""}
      ${e.output?`<pre>${esc(e.output)}</pre>`:""}
    </div>`).join("");
  return `<details class="f" ${f.severity==="blocker"||f.severity==="major"?"open":""}>
    <summary>
      <span class="sev ${f.severity}">${f.severity}</span>
      <span class="rid">${esc(r.id)}</span>
      <span class="ck">${esc(f.checker)}</span>
      <span class="conf">confidence ${f.confidence!=null?f.confidence:"—"}</span>
    </summary>
    <div class="fbody">
      ${r.quote?`<div class="q">“${esc(r.quote)}”<div class="src">${esc(r.source)}</div></div>`:""}
      ${ev}
      ${f.suggested_fix?`<div class="fix"><b>Suggested fix.</b> ${esc(f.suggested_fix)}</div>`:""}
    </div></details>`;
}

function body(){
  const d = DATA.find(x => x.pr === cur);
  const shown = d.findings.filter(f => sev === "all" ? true
              : sev === "problems" ? (f.severity === "blocker" || f.severity === "major") : f.severity === sev);
  const counts = SEVS.map(s => [s, d.findings.filter(f => f.severity === s).length]).filter(x => x[1]);
  document.getElementById("main").innerHTML = `
    <div class="title">#${d.pr} · ${esc(d.title)}</div>
    <div class="meta">by ${esc(d.author)} · opened ${esc(d.opened)} · ${esc(d.state)} ·
      <a href="https://github.com/ScrollPrize/villa/pull/${d.pr}">open it on GitHub</a></div>
    <div class="panel">
      <h3>What the gate said</h3>
      <dl class="kv">
        <dt>Verdict</dt><dd><span class="b ${d.verdict}">${d.verdict}</span></dd>
        <dt>Top reason</dt><dd class="mono">${esc(d.truth.top||"—")}</dd>
        <dt>Findings</dt><dd>${counts.map(c => `${c[1]} ${c[0]}`).join(" · ")}</dd>
      </dl>
    </div>
    <div class="panel truth">
      <h3>What really happened</h3>
      <dl class="kv">
        <dt>Outcome</dt><dd>${esc(d.truth.outcome||"—")}</dd>
        <dt>Why</dt><dd>${esc(d.truth.why||"—")}</dd>
        <dt>Gate correct?</dt><dd><span class="b ${d.truth.agree?"yes":"no"}">${d.truth.agree?"yes":"no"}</span></dd>
        <dt>Repo's own CI</dt><dd>${esc(d.truth.incumbent||"nothing")}</dd>
      </dl>
    </div>
    <div class="filters">
      ${[["all","everything"],["problems","blockers + major"]].concat(counts.map(c=>[c[0],c[0]]))
        .map(f => `<button data-s="${f[0]}" class="${sev===f[0]?"on":""}">${f[1]}</button>`).join("")}
      <span class="count">${shown.length} of ${d.findings.length} shown</span>
    </div>
    ${shown.map(finding).join("") || '<div class="panel">Nothing at this severity.</div>'}`;
  document.querySelectorAll(".filters button").forEach(b =>
    b.onclick = () => { sev = b.dataset.s; body(); });
}
rail(); body();
</script></body></html>
"""


def main():
    data = load()
    OUT.parent.mkdir(exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"))
    OUT.write_text(HTML.replace("__DATA__", payload))
    total = sum(len(d["findings"]) for d in data)
    print(f"wrote {OUT.relative_to(ROOT)} — {len(data)} PRs, {total} findings, {OUT.stat().st_size//1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
