"""Render the mermaid diagrams in docs/10-uml.md to PNG (docs/figures/U0x_*.png).

    .venv/Scripts/python analysis/render_uml.py
Uses Playwright with the installed Chrome and mermaid from the jsdelivr CDN.
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
UML = ROOT / "docs" / "10-uml.md"
OUT = ROOT / "docs" / "figures"
NAMES = {"U01": "U01_class_data_model", "U02": "U02_component_router", "U02M": "U02M_module_interfaces",
         "U03": "U03_class_domain_types", "U04": "U04_sequence_decision", "U05": "U05_activity_training",
         "U06": "U06_state_gui"}
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"


def diagrams() -> dict[str, str]:
    text = UML.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in
            re.finditer(r"<!-- (U\w+) -->\s*```mermaid\n(.*?)```", text, flags=re.S)}


def main() -> None:
    found = diagrams()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=2)
        for key, src in found.items():
            html = f"""<html><body style="margin:0;background:#fff">
<div id="uml-root" class="mermaid" style="display:inline-block;padding:24px"></div>
<script src="{MERMAID}"></script>
<script>
  document.getElementById('uml-root').textContent = {json.dumps(src)};
  mermaid.initialize({{startOnLoad:false, theme:'neutral', securityLevel:'strict', fontFamily:'Arial',
                       themeVariables:{{fontSize:'18px'}},
                       flowchart:{{htmlLabels:true, useMaxWidth:false}}, class:{{useMaxWidth:false}},
                       sequence:{{useMaxWidth:false}}, state:{{useMaxWidth:false}}}});
  mermaid.run({{nodes:[document.getElementById('uml-root')]}}).then(() => document.body.dataset.done = '1')
    .catch(e => {{ document.body.dataset.done = 'err'; document.body.dataset.err = String(e); }});
</script></body></html>"""
            page.set_content(html)
            page.wait_for_function("document.body.dataset.done", timeout=30_000)
            if page.evaluate("document.body.dataset.done") == "err":
                raise RuntimeError(f"{key}: {page.evaluate('document.body.dataset.err')}")
            png = OUT / f"{NAMES[key]}.png"
            page.locator("#uml-root").screenshot(path=str(png))
            print(png.name, png.stat().st_size, "bytes")
        browser.close()


if __name__ == "__main__":
    main()
