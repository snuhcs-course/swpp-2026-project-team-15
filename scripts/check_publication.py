"""Check local Wiki publication sources; never read or write the remote Wiki.

After intentionally editing sources, run with --update-manifest, review the diff,
then run without arguments. Uses only the Python standard library.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/submission/iteration-2"
WIKI = PACKAGE / "wiki"
MANIFEST = PACKAGE / "publication-manifest.json"


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-manifest", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    actual = {
        path.relative_to(WIKI).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(WIKI.rglob("*"))
        if path.is_file()
    }
    known_pages = {Path(name).stem for name in actual if name.endswith(".md")}
    known_pages.update(manifest["preserved_wiki_pages"])
    for path in WIKI.glob("*.md"):
        text = path.read_text()
        for target in re.findall(r"\[\[([^\]]+)\]\]", text):
            page = target.split("|")[-1]
            if page not in known_pages:
                raise SystemExit(f"Unknown Wiki page in {path.name}: {page}")
        for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
            image = (path.parent / target).resolve()
            if not image.is_relative_to(WIKI) or not image.is_file():
                raise SystemExit(f"Missing/outside publication image in {path.name}: {target}")
    original = (ROOT / "docs/acceptance/requirements-2026-10-09.md").read_text()
    prepared = (WIKI / "Requirements-and-Specifications.md").read_text()
    for heading in ("## Functional Requirements", "## Non-functional Requirements"):
        if section(original, heading) != section(prepared, heading):
            raise SystemExit(f"Prepared requirements changed protected source wording: {heading}")
    report = (WIKI / "AI-Collaboration-Report-Iteration-2.md").read_text()
    count = len(report.split())
    if not 500 <= count <= 700 or len(re.findall(r"^## [1-6]\. ", report, re.M)) != 6:
        raise SystemExit(f"AI contribution draft must have six sections and 500–700 words: {count}")
    if args.update_manifest:
        manifest["files"] = actual
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    elif manifest["files"] != actual:
        raise SystemExit(
            "Publication sources differ from manifest; review and update it explicitly"
        )
    print(f"Publication sources verified: {len(actual)} files; AI draft {count} words")
    print("This verifies local consistency, not team approval or official Wiki publication")


if __name__ == "__main__":
    main()
