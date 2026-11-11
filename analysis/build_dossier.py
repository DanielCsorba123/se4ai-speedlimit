"""Build the SpeedLimit dossier artifact (single HTML hub, hash-routed views) from docs/*.md.

Run: python analysis/build_dossier.py  ->  site/index.html (+ site/figures copied)
"""
import html
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITE = ROOT / "site"
(SITE / "figures").mkdir(parents=True, exist_ok=True)
for f in (DOCS / "figures").glob("*.png"):
    shutil.copy(f, SITE / "figures" / f.name)
shutil.copy(DOCS / "_sources" / "main-exercise-slide32.png", SITE / "figures" / "main-exercise-slide32.png")

facts = json.loads((DOCS / "figures" / "facts.json").read_text())

# (hash, file, nav title, perspective)
PAGES = [
    ("charter", "01-project-charter.md", "Project Charter", "Project Lead"),
    ("requirements", "02-requirements-specification.md", "Requirements Spec", "Requirements Eng."),
    ("data", "03-data-analysis-report.md", "Data Analysis Report", "Data Science"),
    ("architecture", "04-solution-architecture.md", "Solution Architecture", "Architecture & ML"),
    ("decisions", "05-decision-log.md", "Decision Log", "Project Lead"),
    ("risks", "06-risk-issue-register.md", "Risks & Issues", "QA & Risk"),
    ("tests", "07-test-strategy.md", "Test Strategy", "QA"),
    ("backlog", "superpowers/plans/2026-11-10-speedlimit-mvp.md", "Task Backlog", "Project Lead"),
    ("storyline", "08-presentation-storyline.md", "Presentation Storyline", "Project Lead"),
    ("lessons", "09-lessons-learned.md", "Lessons Learned", "Project Lead"),
]

CAPTIONS = {
    "F01": "Raw readings file. Semicolon separator, decimal comma and a UTF-8 BOM. The speed limit is not a column: it is hidden as a reading of the pseudo-sensor -1.",
    "F02": "SensorTypes.csv uses the code T for both temperature and traffic, has a trailing space in 'W ', a unit typo 'hm/h' and a padded unit. A join on the code breaks silently.",
    "F03": "Sensor coverage. Sensors 7, 10 and 17 are documented but never report (so no air pressure). Sensor 19 reports every hour but is not documented.",
    "F04": "The REQ1 reality check. At every observed speed limit and condition, near-accidents average more than 1 per hour. Lower limits show more incidents, which points to confounding: operators lowered the limit when conditions were worse.",
    "F05": "The two files use different clocks. Readings use 0-23, accidents use 1-24 with 44 events at hour 24. We map accident hour h to reading hour h-1 (D1).",
    "F06": "Sensor 16 carries code T but does not track the temperature sensors (corr. 0.21). Its range of 1.85-30 fits traffic in cars per second. Sensors 15, 18 and 19 agree at r >= 0.996.",
    "F07": "Hours with a reduced limit although it was light, the road was dry and REQ3 demands 80 km/h. 28 such hours in January, all during daytime (06-18h).",
    "F08": "Illuminance spans six orders of magnitude. On a log scale day and night separate cleanly, and the SPEC1 threshold of 500 millilux sits in the gap. The model gets log10(lux).",
    "F09": "Composition of the event log. 964 near-accidents against 32 accidents. Almost 9 out of 10 near-misses are 'too close to another car'.",
    "F10": "The year N+1 readings file is the year N file without its header: all 12,648 rows are identical. A drift check will find nothing, so the verdict is no retraining.",
    "F11": "First week of January. Light, water and temperature with their SPEC thresholds, against the speed limit actually set (black) and near-accidents per hour (red).",
    "F12": "The course's error list (deck slide 17) checked against the V100 files. Four structural issues are present. The eight row-level faults are not, so the pipeline handles them via injected-fault tests (D19).",
}
FIG_TITLES = {
    "F01": "Raw file format", "F02": "Sensor type metadata", "F03": "Sensor coverage",
    "F04": "REQ1 vs data", "F05": "Clock mismatch", "F06": "Code T ambiguity",
    "F07": "Unexplained reductions", "F08": "Log-scale light", "F09": "Event composition",
    "F10": "Year N+1 = Year N", "F11": "Week overview", "F12": "Slide-17 error check",
}
figs = sorted(p.name for p in (DOCS / "figures").glob("F*.png"))


def md_to_html(text: str) -> str:
    text = re.sub(r"\]\((?:\.\./)*(?:docs/)?figures/", "](figures/", text)
    out = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
                            extension_configs={"toc": {"permalink": False}})
    out = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                 lambda m: f'<pre class="mermaid">{m.group(1)}</pre>', out, flags=re.S)
    out = out.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    out = re.sub(r'<img alt="([^"]*)" src="(figures/[^"]+)"\s*/?>',
                 r'<figure class="docfig"><img alt="\1" src="\2" loading="lazy"><figcaption>\1</figcaption></figure>', out)
    # internal md links -> hash routes
    for h, f, *_ in PAGES:
        base = Path(f).name
        out = out.replace(f'href="{base}"', f'href="#{h}"').replace(f'href="./{base}"', f'href="#{h}"')
        out = re.sub(rf'href="[^"]*{re.escape(base)}(#[^"]*)?"', f'href="#{h}"', out)
    out = re.sub(r'<input type="checkbox"[^>]*>', "", out)
    out = out.replace("[ ]", '<span class="box" aria-hidden="true"></span>')
    return out


def toc_of(h: str) -> list[tuple[str, str]]:
    return re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', h)


sections, nav, missing = [], [], []
for h, f, title, persp in PAGES:
    p = DOCS / f
    if not p.exists():
        missing.append(f)
        continue
    body = md_to_html(p.read_text(encoding="utf-8"))
    body = re.sub(r'id="([^"]+)"', lambda m: f'id="{h}--{m.group(1)}"', body)
    toc = toc_of(body)
    lines = len(p.read_text(encoding="utf-8").splitlines())
    toc_html = "".join(f'<li><button type="button" data-jump="{i}">{re.sub("<.*?>", "", t)}</button></li>' for i, t in toc)
    sections.append(f'''<section class="view doc" data-view="{h}" hidden>
  <div class="doc-head"><span class="persp">{html.escape(persp)}</span><span class="src">docs/{html.escape(f)} · {lines} lines</span></div>
  <div class="doc-grid"><article class="prose">{body}</article>
  <aside class="toc"><p class="toc-label">On this page</p><ol>{toc_html}</ol></aside></div>
</section>''')
    nav.append((h, title, persp))

# ---- overview -------------------------------------------------------------
rates = [r["mean_near_per_h"] for r in facts["near_by_cond_speed"]]
tiles = [
    ("744", "hours of data", "January only, 17 live sensors"),
    (f"{facts['near_accidents']}", "near-accidents", f"plus {facts['accidents']} accidents"),
    (f"{min(rates):.2f}–{max(rates):.2f}", "near-accidents / h", "at any limit. REQ1 target is ≤ 1"),
    (f"{facts['corr_near_vs_speed']:.3f}", "correlation", "near-accidents vs speed limit"),
    (f"{facts['n1_identical_rows']:,}", "identical rows", "year N+1 = year N"),
]
tiles_html = "".join(f'<div class="tile"><b>{a}</b><span>{b}</span><small>{c}</small></div>' for a, b, c in tiles)

findings = [
    ("critical", "F04", "The data barely supports REQ1",
     "Near-accidents stay above 1/h at every limit. We build to the requirement anyway, with a monotonicity guard and an honest 'target not reachable' flag (D7–D9)."),
    ("critical", "F10", "Year N+1 is a copy of year N",
     "The retraining exercise has no new signal. We ship the drift check and report 'no retraining' (D13)."),
    ("major", "F05", "Accidents and readings use different clocks",
     "Hours 1–24 against 0–23. Mapped as h−1 (D1). A wrong choice shifts every label by one hour."),
    ("major", "F06", "One code, two meanings",
     "Code T is both temperature and traffic. Resolved by behaviour: 16 is traffic, 15/18/19 are temperature (D2)."),
    ("major", "F07", "28 reductions without a reason",
     "Daytime hours set below 80 although REQ3 says 80. Kept for training, never output (D10)."),
    ("minor", "F03", "Silent and undocumented sensors",
     "7, 10 and 17 never report, so there is no air-pressure feature. 19 is undocumented but clearly temperature (D3)."),
]
find_html = "".join(f'''<button type="button" class="finding sev-{s}" data-fig="{fid}">
  <span class="sev">{s}</span><img src="figures/{next(x for x in figs if x.startswith(fid))}" alt="" loading="lazy">
  <span class="ft">{t}</span><span class="fd">{d}</span><span class="fref">{fid} · open evidence</span></button>''' for s, fid, t, d in findings)

doc_cards = "".join(f'<a class="dcard" href="#{h}"><span class="persp">{html.escape(p)}</span><b>{html.escape(t)}</b></a>'
                    for h, t, p in nav)

overview = f'''<section class="view" data-view="overview">
  <header class="hero">
    <div class="sign" aria-hidden="true"><span>80</span></div>
    <div><p class="eyebrow">SE4AI · Case study SpeedLimit · ExID SpeedLimit21</p>
    <h1>SpeedLimit Project Dossier</h1>
    <p class="lede">Everything we know before writing code: the brief, the requirements, what the data really says, the design, the risks, the plan and the story for management. Status: <strong>recon complete, build not started</strong> (2026-11-10).</p></div>
  </header>
  <div class="tiles">{tiles_html}</div>
  <h2 class="sec">Key findings</h2>
  <p class="sec-sub">Click a finding to open its evidence. Every figure is a presentation-ready PNG in <code>docs/figures/</code>.</p>
  <div class="findings">{find_html}</div>
  <h2 class="sec">How the system decides</h2>
<pre class="mermaid">flowchart LR
  IN[Sensor inputs<br/>GUI or replay] --> R{{Condition rules<br/>SPEC1 / SPEC2}}
  R -- dark or black ice --> NN[Neural network<br/>sweep 40..80, guard]
  R -- neither --> D80[80 km/h<br/>REQ3]
  AQ[Air-quality forecast<br/>Open-Meteo] --> P{{Poor air?}}
  P -- yes --> LLM[LLM advice<br/>JSON + fallback]
  NN --> MIN[[min of all reasons]]
  LLM --> MIN
  D80 --> MIN
  MIN --> OUT[Speed limit<br/>+ explanation + audit]</pre>
  <h2 class="sec">Documents</h2>
  <p class="sec-sub">Written from five team perspectives. Decisions D1–D20 bind them together.</p>
  <div class="dcards">{doc_cards}</div>
  <h2 class="sec">The assignment</h2>
  <figure class="docfig narrow"><img src="figures/main-exercise-slide32.png" alt="Main home exercise slide" loading="lazy"><figcaption>Main home exercise (deck slide 32): implement training + operational stage, then present to management.</figcaption></figure>
</section>'''

gallery = "".join(f'''<figure class="gcard" id="g-{n[:3]}"><button type="button" class="zoom" data-src="figures/{n}" aria-label="Enlarge {n[:3]}"><img src="figures/{n}" alt="{FIG_TITLES.get(n[:3], n)}" loading="lazy"></button>
<figcaption><span class="fid">{n[:3]}</span> <b>{FIG_TITLES.get(n[:3], "")}</b><span>{CAPTIONS.get(n[:3], "")}</span><code>docs/figures/{n}</code></figcaption></figure>''' for n in figs)
evidence = f'''<section class="view" data-view="evidence" hidden>
  <p class="eyebrow">Presentation evidence</p><h1>Evidence Gallery</h1>
  <p class="lede">Twelve screenshots of the data, rendered at 150 dpi for slides. Regenerate any time with <code>python analysis/make_figures.py</code>. Numbers come from <code>docs/figures/facts.json</code>.</p>
  <div class="gallery">{gallery}</div>
</section>'''

nav_html = ('<a href="#overview" data-nav="overview">Overview</a><a href="#evidence" data-nav="evidence">Evidence Gallery</a>'
            '<p class="nav-label">Documents</p>' +
            "".join(f'<a href="#{h}" data-nav="{h}">{html.escape(t)}<small>{html.escape(p)}</small></a>' for h, t, p in nav))

tpl = (ROOT / "analysis" / "dossier_template.html").read_text(encoding="utf-8")
page = (tpl.replace("{{NAV}}", nav_html)
           .replace("{{VIEWS}}", overview + evidence + "\n".join(sections)))
(SITE / "index.html").write_text(page, encoding="utf-8")
print("built", SITE / "index.html", f"{len(page) / 1024:.0f} KB", "missing:", missing)
