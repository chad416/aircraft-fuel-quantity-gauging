#!/usr/bin/env python3
"""Export DOSSIER.md to DOSSIER.pdf: Markdown -> HTML (python-markdown) -> PDF
(PyMuPDF Story layout; no browser needed).

    python tools/make_pdf.py
"""

import os
import re
import tempfile

import markdown
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
body { font-family: sans-serif; font-size: 9pt; line-height: 1.3; }
h1 { font-size: 15pt; color: #1d4e6e; }
h2 { font-size: 12pt; color: #2a6f97; margin-top: 12pt; }
h3 { font-size: 10pt; margin-top: 8pt; }
table { border-collapse: collapse; font-size: 7.5pt; margin-top: 3pt; margin-bottom: 3pt; }
th, td { border: 0.5px solid #999; padding: 1.5pt 3pt; }
th { background-color: #eef3f7; }
code { font-family: monospace; font-size: 7.5pt; }
pre { font-family: monospace; font-size: 7pt; background-color: #f4f4f4; }
img { width: 100%; }
"""


LIST = re.compile(r"^(\s*)([-*]|\d+\.)\s")


def for_python_markdown(src):
    """GitHub accepts a list right after a paragraph line and 2-space nesting;
    python-markdown needs a blank line before the list and 4-space nesting."""
    out = []
    in_code = False
    for line in src.split(chr(10)):
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else LIST.match(line)
        if m:
            indent = len(m.group(1))
            line = " " * (2 * indent) + line.lstrip(" ")
            prev = out[-1] if out else ""
            if prev.strip() and not LIST.match(prev) and not prev.startswith(" "):
                out.append("")
        elif not in_code and line.startswith("  ") and out and LIST.match(out[-1]):
            line = "  " + line  # continuation lines of a nested item
        out.append(line)
    return chr(10).join(out)


def main():
    src = for_python_markdown(open(os.path.join(ROOT, "DOSSIER.md"), encoding="utf-8").read())
    body = markdown.markdown(src, extensions=["tables", "fenced_code", "sane_lists"])
    story = pymupdf.Story(html=body, user_css=CSS, archive=pymupdf.Archive(ROOT))
    out = os.path.join(ROOT, "DOSSIER.pdf")
    tmp = os.path.join(tempfile.gettempdir(), "dossier_uncompressed.pdf")
    writer = pymupdf.DocumentWriter(tmp)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (42, 48, -42, -48)
    more = True
    pages = 0
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
        pages += 1
    writer.close()
    # page numbers, then a compressed save (Story embeds images uncompressed)
    doc = pymupdf.open(tmp)
    for i, page in enumerate(doc):
        page.insert_text(
            (mediabox.width / 2 - 20, mediabox.height - 24),
            "%d / %d" % (i + 1, len(doc)),
            fontsize=7,
            color=(0.4, 0.4, 0.4),
        )
    doc.save(out, garbage=4, deflate=True, deflate_images=True)
    doc.close()
    try:
        os.remove(tmp)
    except OSError:
        pass  # Windows may still hold the file; it is in the temp folder
    print("wrote", out, pages, "pages", os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
