"""Generate local HTML/PDF previews from the single Wiki source directory.

Requires pandoc, Google Chrome (or --browser) and pdfinfo on PATH. Outputs are
previews, never evidence of official Wiki publication or eTL submission.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "docs/submission/iteration-2/wiki"
DOCUMENTS = {
    "Requirements-and-Specifications": "team15-iter2-reqspec",
    "Design-Documentation": "team15-iter2-design",
    "Testing-Documentation": "team15-iter2-testing",
    "AI-Collaboration-Report-Iteration-2": "team15-iter2-AI-collaboration-report",
}
CSS = """
body{font-family:Arial,"Noto Sans CJK KR",sans-serif;font-size:10pt;line-height:1.35}
h1{font-size:21pt}h2{font-size:14pt;break-after:avoid}h3{font-size:11pt;break-after:avoid}
table{border-collapse:collapse;width:100%;font-size:8.5pt}
td,th{border:1px solid #aab5ae;padding:4px;text-align:left;vertical-align:top}
tr{break-inside:avoid}thead{display:table-header-group}
pre{font-size:8pt;white-space:pre-wrap;overflow-wrap:anywhere;padding:7px}
img{max-width:100%;height:auto}@page{size:A4;margin:14mm}
"""
AI_CSS = """
body{font-size:8.5pt;line-height:1.05}h1{font-size:14pt;margin:0 0 4pt}
h2{font-size:10pt;margin:5pt 0 2pt}p{margin:3pt 0}
ul{margin:3pt 0;padding-left:15pt}@page{margin:10mm}
"""


def wiki_link(match: re.Match) -> str:
    parts = match.group(1).split("|", 1)
    label, target = parts if len(parts) == 2 else (parts[0], parts[0])
    return f"[{label}](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/{target})"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/iteration2-preview")
    parser.add_argument("--browser", default="google-chrome")
    args = parser.parse_args()
    for tool in ("pandoc", "pdfinfo", args.browser):
        if not shutil.which(tool):
            raise SystemExit(f"Required preview tool not found: {tool}")
    subprocess.run([sys.executable, str(ROOT / "scripts/check_publication.py")], check=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = {}
    with (output / "export.log").open("w") as log:
        for stem, name in DOCUMENTS.items():
            original = WIKI / (stem + ".md")
            text = re.sub(r"\[\[([^\]]+)\]\]", wiki_link, original.read_text())
            text = text.replace("](images/", "](" + str(WIKI / "images") + "/")
            markdown, html, pdf = (output / (name + suffix) for suffix in (".md", ".html", ".pdf"))
            markdown.write_text(text)
            subprocess.run(
                [
                    "pandoc",
                    "-f",
                    "gfm",
                    "-t",
                    "html5",
                    "--standalone",
                    str(markdown),
                    "-o",
                    str(html),
                ],
                check=True,
                stdout=log,
                stderr=log,
            )
            style = CSS + (AI_CSS if stem.startswith("AI-") else "")
            html.write_text(html.read_text().replace("</head>", f"<style>{style}</style></head>"))
            subprocess.run(
                [
                    args.browser,
                    "--headless",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    "--print-to-pdf=" + str(pdf),
                    html.as_uri(),
                ],
                check=True,
                stdout=log,
                stderr=log,
            )
            info = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
            pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
            if stem.startswith("AI-") and pages != 1:
                raise SystemExit(
                    "AI preview exceeds one page; shorten within the 500–700 word range"
                )
            sources[pdf.name] = {
                "source": original.relative_to(ROOT).as_posix(),
                "source_sha256": digest(original),
                "pdf_sha256": digest(pdf),
                "pages": pages,
            }
            print(f"{pdf.name}: {pages} page(s)")
    baseline = json.loads((WIKI.parent / "publication-manifest.json").read_text())[
        "official_baseline"
    ]
    provenance = {
        "status": "local previews; not official Wiki exports or eTL submissions",
        "official_baseline": baseline,
        "sources": sources,
    }
    (output / "export-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
