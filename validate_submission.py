"""
validate_submission.py — Redrob submission CSV validator.

Usage:
    python validate_submission.py submission.csv
"""
from __future__ import annotations
import csv
import sys
from pathlib import Path


def validate(path: str) -> bool:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: File not found: {path}")
        return False

    required_cols = {"candidate_id", "rank", "score", "reasoning"}
    errors = []

    with open(p, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("ERROR: File is empty or has no header.")
            return False

        missing = required_cols - set(reader.fieldnames)
        if missing:
            print(f"ERROR: Missing columns: {missing}")
            return False

        rows = list(reader)

    if len(rows) != 100:
        errors.append(f"Expected exactly 100 rows, got {len(rows)}")

    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()

    for i, row in enumerate(rows, start=1):
        cid   = row.get("candidate_id", "").strip()
        rank  = row.get("rank", "").strip()
        score = row.get("score", "").strip()
        rsn   = row.get("reasoning", "").strip()

        if not cid:
            errors.append(f"Row {i}: empty candidate_id")
        if cid in seen_ids:
            errors.append(f"Row {i}: duplicate candidate_id {cid!r}")
        seen_ids.add(cid)

        try:
            r = int(rank)
            if r in seen_ranks:
                errors.append(f"Row {i}: duplicate rank {r}")
            seen_ranks.add(r)
        except ValueError:
            errors.append(f"Row {i}: rank {rank!r} is not an integer")

        try:
            s = float(score)
            if not (0.0 <= s <= 1.0):
                errors.append(f"Row {i}: score {s} out of [0,1]")
        except ValueError:
            errors.append(f"Row {i}: score {score!r} is not a float")

        if not rsn:
            errors.append(f"Row {i}: empty reasoning")

    expected_ranks = set(range(1, len(rows) + 1))
    if seen_ranks != expected_ranks:
        errors.append(f"Ranks are not a contiguous 1..{len(rows)} sequence")

    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        print(f"\nSubmission is INVALID ({len(errors)} error(s)).")
        return False

    print(f"Submission is valid. {len(rows)} rows, scores in range.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_submission.py <submission.csv>")
        sys.exit(1)
    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 1)
