# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""CSV helpers shared by append and build acceptance tests."""

import csv


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
