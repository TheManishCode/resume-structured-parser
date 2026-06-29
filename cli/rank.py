"""
cli/rank.py — Batch candidate ranker (CLI mode).

Uses the same deterministic scoring engine as the web API
(packages/core/scoring/) so CLI and API results are identical.

Usage:
    python cli/rank.py candidates.jsonl submission.csv
    python cli/rank.py candidates.jsonl.gz submission.csv --debug
"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import sys
import time
import tracemalloc
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.core.scoring import score_candidate, generate_reasoning
from packages.core.scoring import schema as _schema
from packages.core.scoring import integrity, role_taxonomy, disqualifiers, behavioral

TOP_N       = 100
MAX_SECONDS = 270


def _open_dataset(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _score_all(path: Path) -> list[dict]:
    results = []
    for line in _open_dataset(path):
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)

        tax  = role_taxonomy.role_taxonomy(c)
        intg = integrity.integrity_check(c)
        dq   = disqualifiers.disqualifier_check(c)
        beh  = behavioral.behavioral_score(c)
        from packages.core.scoring.scoring import compute_score
        sc   = compute_score(c, tax, intg, dq, beh)
        rsn  = generate_reasoning(c, tax, dq, beh, sc)

        results.append({
            "candidate_id": _schema.get_candidate_id(c),
            "score":        sc["score"],
            "reasoning":    rsn,
            "sub_scores":   sc["sub_scores"],
        })
    return results


def _select_top(results: list[dict], n: int) -> list[dict]:
    results.sort(key=lambda r: (-r["score"], r["candidate_id"]))
    return results[:n]


def _write_csv(top: list[dict], out_path: Path) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, row in enumerate(top, start=1):
            writer.writerow([row["candidate_id"], rank, f"{row['score']:.6f}", row["reasoning"]])


def _write_debug_csv(results: list[dict], out_path: Path) -> None:
    debug_path = out_path.parent / (out_path.stem + "_debug_all.csv")
    results_sorted = sorted(results, key=lambda r: (-r["score"], r["candidate_id"]))
    with open(debug_path, "w", newline="", encoding="utf-8") as f:
        if not results_sorted:
            return
        sub_keys = list(results_sorted[0].get("sub_scores", {}).keys())
        header = ["rank", "candidate_id", "score"] + sub_keys + ["reasoning"]
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for rank, row in enumerate(results_sorted[:5000], start=1):
            d = {"rank": rank, "candidate_id": row["candidate_id"],
                 "score": f"{row['score']:.6f}", "reasoning": row["reasoning"]}
            d.update(row.get("sub_scores", {}))
            writer.writerow(d)
    print(f"  Debug CSV (top-5000): {debug_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranker (CLI)")
    parser.add_argument("dataset", help="Path to candidates.jsonl or candidates.jsonl.gz")
    parser.add_argument("output",  help="Output CSV path (e.g. submission.csv)")
    parser.add_argument("--top",   type=int, default=TOP_N, help="Number of candidates to output")
    parser.add_argument("--debug", action="store_true", help="Write debug CSV with all sub-scores")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    out_path     = Path(args.output)

    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    tracemalloc.start()
    t0 = time.time()

    print(f"Loading and scoring: {dataset_path}")
    results = _score_all(dataset_path)

    elapsed_score = time.time() - t0
    print(f"  Scored {len(results):,} candidates in {elapsed_score:.1f}s")

    if elapsed_score > MAX_SECONDS:
        print(
            f"WARNING: Runtime {elapsed_score:.0f}s > soft limit {MAX_SECONDS}s "
            f"(hard limit: 300s).",
            file=sys.stderr,
        )

    top = _select_top(results, args.top)
    _write_csv(top, out_path)

    if args.debug:
        _write_debug_csv(results, out_path)

    elapsed = time.time() - t0
    current_mb, peak_mb = (x / 1024 / 1024 for x in tracemalloc.get_traced_memory())
    tracemalloc.stop()

    print(f"  Written: {out_path}")
    if top:
        print(f"  Top-{len(top)} score range: {top[0]['score']:.4f} to {top[-1]['score']:.4f}")
    print(f"  Total time: {elapsed:.1f}s | Peak memory: {peak_mb:.0f}MB")
    print()
    print("Top 10 ranked candidates:")
    for rank_num, r in enumerate(top[:10], start=1):
        print(f"  Rank {rank_num:2d} | {r['candidate_id']} | "
              f"score={r['score']:.4f} | {r['reasoning'][:80]}")


if __name__ == "__main__":
    main()
