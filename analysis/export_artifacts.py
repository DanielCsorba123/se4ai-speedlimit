"""Export the two claude.ai artifacts to files anyone can open from GitHub.

    .venv/Scripts/python analysis/export_artifacts.py
Writes docs/exports/:
  SpeedLimit_Management_Deck.pdf   - 16:9 slides, one per page
  SpeedLimit_Management_Deck.pptx  - same slides as pictures, speaker notes attached
  SpeedLimit_Project_Dossier.pdf   - every dossier page incl. rendered mermaid diagrams
Run `python analysis/build_dossier.py` first so site/index.html is current.
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.util import Emu

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "docs" / "presentation" / "project"
OUT = ROOT / "docs" / "exports"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
ICONS = {"Lock": "&#128274;", "Warning": "&#9888;", "Chart": "&#128200;", "Check": "&#10003;"}

SLIDE_CSS = """
* { margin: 0; box-sizing: border-box; }
body { background: #555; }
section { position: relative; width: 1920px; height: 1080px; overflow: hidden; page-break-after: always; }
section > aside { display: none; }
h1 { font-size: 96px; } h2 { font-size: 64px; } h3 { font-size: 44px; } p { font-size: 32px; line-height: 1.4; }
ul { padding-left: 1.2em; }
table { border-collapse: collapse; }
th, td { padding: 0.35em 0.6em; border-bottom: 1px solid #C9CFC8; text-align: left; vertical-align: top; }
th { font-weight: 600; border-bottom: 2px solid #1C2731; }
x-icon { display: inline-block; font-style: normal; line-height: 1; }
@page { size: 1920px 1080px; margin: 0; }
"""


def deck_html() -> tuple[str, list[str]]:
    index = json.loads((DECK / "deck.json").read_text(encoding="utf-8"))
    assets = json.loads((ROOT / "docs" / "presentation" / "assets.json").read_text(encoding="utf-8"))
    fonts = "".join(f'<link rel="stylesheet" href="{f["href"]}">' for f in index["faces"].values() if "href" in f)
    slides, notes = [], []
    for sid in index["order"]:
        html = (DECK / "slides" / f"{sid}.html").read_text(encoding="utf-8")
        for blob, path in assets.items():
            html = html.replace(f'src="{blob}"', f'src="{(ROOT / path).as_uri()}"')
        html = re.sub(r'<x-icon name="(\w+)" style="([^"]*)"></x-icon>',
                      lambda m: f'<x-icon style="{m.group(2)};font-size:48px">{ICONS.get(m.group(1), "")}</x-icon>', html)
        note = re.search(r"<aside>(.*?)</aside>", html, flags=re.S)
        notes.append(note.group(1).strip() if note else "")
        slides.append(html)
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>{index['title']}</title>{fonts}"
            f"<style>{SLIDE_CSS}</style></head><body>{''.join(slides)}</body></html>")
    return page, notes


def export_deck(p) -> None:
    page_html, notes = deck_html()
    tmp = OUT / "_deck_render.html"
    tmp.write_text(page_html, encoding="utf-8")
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(tmp.as_uri())
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.pdf(path=str(OUT / "SpeedLimit_Management_Deck.pdf"), width="1920px", height="1080px",
             print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
    pngs = []
    for i, sec in enumerate(page.locator("section").all()):
        png = OUT / f"_slide_{i + 1:02d}.png"
        sec.screenshot(path=str(png))
        pngs.append(png)
    browser.close()

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)          # 16:9
    for png, note in zip(pngs, notes):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(str(png), 0, 0, width=prs.slide_width, height=prs.slide_height)
        if note:
            s.notes_slide.notes_text_frame.text = note
    prs.save(str(OUT / "SpeedLimit_Management_Deck.pptx"))
    for png in pngs:
        png.unlink()
    tmp.unlink()


def export_dossier(p) -> None:
    site = ROOT / "site" / "index.html"
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(site.as_uri())
    page.add_style_tag(content="""
        .view[hidden] { display: block !important; }
        .view { page-break-before: always; animation: none !important; }
        nav.gantry, .toc, .lightbox { display: none !important; }
        .shell { display: block !important; }
        .doc-grid { display: block !important; }
        .finding, .gcard, .docfig, table, tr, pre { break-inside: avoid; }
    """)
    page.add_script_tag(url=MERMAID)
    page.evaluate("""async () => {
        mermaid.initialize({startOnLoad: false, theme: 'neutral', securityLevel: 'strict'});
        await mermaid.run({querySelector: 'pre.mermaid'});
    }""")
    page.wait_for_timeout(1500)
    page.emulate_media(media="print")
    page.pdf(path=str(OUT / "SpeedLimit_Project_Dossier.pdf"), format="A4", print_background=True,
             margin={"top": "14mm", "right": "12mm", "bottom": "14mm", "left": "12mm"})
    browser.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        export_deck(p)
        export_dossier(p)
    for f in sorted(OUT.glob("SpeedLimit_*")):
        print(f.name, f"{f.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
