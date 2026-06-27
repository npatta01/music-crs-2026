"""Reproducible driver for the `anchor-arbiter` Opus subagent.

The Opus arbiter runs on a CC plan (free) but a subagent has a bounded context, so large conflict sets
are split into chunks; each chunk is judged by one `anchor-arbiter` invocation; the chunk outputs are
merged into a single axis-level arbiter file for compose_labels.py --arbiter.

  # 1) split the conflicts_sheet (emitted by compose_labels) into subagent-sized chunks
  python scripts/rerank/anchor_labels/run_arbiter.py chunk --conflicts <dir>/conflicts_sheet.jsonl \
      --work-dir <dir>/arbiter --size 150
  #    -> writes <dir>/arbiter/chunk_000.jsonl ... and prints the exact Agent calls to run.

  # 2) (the orchestrator runs the anchor-arbiter subagent on each chunk, writing arb_000.json ...)

  # 3) merge the chunk outputs + verify full coverage of the conflict set
  python scripts/rerank/anchor_labels/run_arbiter.py merge --conflicts <dir>/conflicts_sheet.jsonl \
      --work-dir <dir>/arbiter --out <dir>/arbiter.json
"""
from __future__ import annotations
import argparse, glob, json, os


def chunk(a):
    rows = [json.loads(l) for l in open(a.conflicts)]
    os.makedirs(a.work_dir, exist_ok=True)
    n = 0
    for i in range(0, len(rows), a.size):
        part = rows[i:i + a.size]
        cf = os.path.join(a.work_dir, f"chunk_{n:03d}.jsonl")
        with open(cf, "w") as f:
            for r in part:
                f.write(json.dumps(r) + "\n")
        n += 1
    print(f"{len(rows)} conflicts -> {n} chunk(s) of <= {a.size} in {a.work_dir}")
    print("\nRun the anchor-arbiter subagent once per chunk (Agent tool, subagent_type='anchor-arbiter'):")
    for j in range(n):
        cf = os.path.join(a.work_dir, f"chunk_{j:03d}.jsonl")
        of = os.path.join(a.work_dir, f"arb_{j:03d}.json")
        print(f"  • INPUT {cf}  ->  OUTPUT {of}")
    print(f"\nThen: python scripts/rerank/anchor_labels/run_arbiter.py merge --conflicts {a.conflicts} "
          f"--work-dir {a.work_dir} --out {os.path.join(os.path.dirname(a.conflicts), 'arbiter.json')}")


def merge(a):
    merged = {}
    for p in sorted(glob.glob(os.path.join(a.work_dir, "arb_*.json"))):
        d = json.load(open(p))
        dup = set(merged) & set(d)
        if dup:
            print(f"  WARN {len(dup)} duplicate keys in {os.path.basename(p)} (last wins)")
        merged.update(d)
    want = {f"{r['sid']}|{r['tn']}" for r in (json.loads(l) for l in open(a.conflicts))}
    missing = want - set(merged)
    extra = set(merged) - want
    json.dump(merged, open(a.out, "w"))
    print(f"merged {len(merged)} arbiter verdicts -> {a.out}")
    print(f"  conflicts to cover: {len(want)} | covered: {len(want & set(merged))} | "
          f"MISSING: {len(missing)} | extra: {len(extra)}")
    if missing:
        print(f"  ❌ NOT all conflicts arbitrated — re-run the arbiter on: {sorted(missing)[:5]}...")
        print(f"     (compose_labels will mark these UNRESOLVED until covered)")
    else:
        print("  ✅ full coverage — feed to compose_labels.py --arbiter " + a.out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chunk"); c.add_argument("--conflicts", required=True)
    c.add_argument("--work-dir", required=True); c.add_argument("--size", type=int, default=150)
    c.set_defaults(fn=chunk)
    m = sub.add_parser("merge"); m.add_argument("--conflicts", required=True)
    m.add_argument("--work-dir", required=True); m.add_argument("--out", required=True)
    m.set_defaults(fn=merge)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
