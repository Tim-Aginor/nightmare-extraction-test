#!/usr/bin/env python3
"""Regression test: hallucination_analysis must be deterministic.

Runs the analyzer twice in fresh subprocesses with different
PYTHONHASHSEED values and asserts byte-identical output. Originally
caught a stale-cache bug (2026-05-11): a module-level cache keyed on
id(universe) leaked across packets when Python recycled memory
addresses, producing 0-3.3pp string-rate noise that varied with the
hash seed.

The structural fix (precompute compact/token sets at universe build
time, no module-level cache) removed the underlying fragility. This
test exists so any future regression - a new id()-keyed cache, an
iteration-order-sensitive bucket, etc. - is caught immediately instead
of contaminating a publishable rate by ±2pp.

Usage:
    python scripts/determinism_test.py                 # uses $PWD
    python scripts/determinism_test.py --workspace ./phase3_default

Exit codes:
    0  byte-identical across hash seeds, with rate spread = 0.00pp
    1  outputs differ (bug reintroduced or new nondeterminism)
    2  workspace missing ground_truth/ or results/

Cost: ~30s per pass against a 5-packet/15-model workspace. Fast enough
to run pre-publish; cheap enough for CI on any branch that touches the
analyzer.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ANALYZER = SCRIPT_DIR / "hallucination_analysis.py"

# Four hash seeds, chosen empirically (2026-05-11) to produce four
# distinct set-iteration orders on a sample of universe-style strings
# ('preston', 'dallas', 'tower', ...). A pair of seeds isn't enough — an
# earlier (0, 1000003) pair happened to produce the same iteration order
# for the actual phase3_default universe, so a deliberately-injected
# nondeterminism was missed. Four seeds gives ≥6 pairwise comparisons,
# enough to surface order-sensitivity on any non-trivial universe.
# Specific values keep the test reproducible across CI runs.
HASH_SEEDS = ["0", "1", "42", "31337"]


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _discover_models(results_dir: Path) -> list[str]:
    """Subdirs of results/ that contain extraction_*.json are model dirs.
    The extraction-file gate skips sibling dirs like results/analysis/
    that the report-generator drops alongside the model dirs."""
    out = []
    for d in sorted(results_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if any(d.glob("extraction_*.json")):
            out.append(d.name)
    return out


def _run(seed: str, gt: Path, results: Path, out: Path,
         models: list[str]) -> None:
    env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
    subprocess.run(
        [sys.executable, str(ANALYZER),
         "--ground-truth", str(gt),
         "--results", str(results),
         "--output", str(out),
         "--models", *models],
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _summarize_diff(a: dict, b: dict) -> list[str]:
    """Per-model rate deltas when outputs disagree, so the failure
    message points at the model/rate that diverged instead of dumping a
    full JSON diff."""
    lines = []
    for m in sorted(set(a) | set(b)):
        if m == "analysis":
            continue
        oa = a.get(m, {}).get("aggregate", {}).get("overall")
        ob = b.get(m, {}).get("aggregate", {}).get("overall")
        if not (oa and ob):
            lines.append(f"  {m}: present in only one run")
            continue
        for k in ("strings_checked", "strings_hallucinated",
                  "numbers_checked", "numbers_hallucinated"):
            if oa.get(k) != ob.get(k):
                lines.append(f"  {m}.{k}: {oa.get(k)} != {ob.get(k)}")
    return lines


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", default=".",
                   help="dir containing ground_truth/ and results/")
    args = p.parse_args()

    ws = Path(args.workspace).resolve()
    gt = ws / "ground_truth"
    results = ws / "results"
    if not gt.is_dir() or not results.is_dir():
        print(f"FAIL: missing {gt} or {results}", file=sys.stderr)
        return 2

    models = _discover_models(results)
    if not models:
        print(f"FAIL: no model dirs under {results}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="determinism_test_") as td:
        td = Path(td)
        outs = []
        for seed in HASH_SEEDS:
            out = td / f"hall_seed_{seed}.json"
            print(f"  running with PYTHONHASHSEED={seed}...", flush=True)
            _run(seed, gt, results, out, models)
            outs.append(out)

        digests = [_sha256(o) for o in outs]
        if len(set(digests)) == 1:
            print(f"PASS: {len(HASH_SEEDS)} runs across "
                  f"{len(models)} models produced byte-identical output")
            print(f"  sha256: {digests[0][:16]}")
            return 0

        # Mismatch: report which model + which counter diverged on the
        # first divergent pair, so the operator can find the new bug
        # without manually diffing four JSONs.
        for i, di in enumerate(digests):
            print(f"  PYTHONHASHSEED={HASH_SEEDS[i]}: sha={di[:16]}",
                  file=sys.stderr)
        # Pick the first pair that differs for the field-level dump
        ai_bi = next(((i, j) for i in range(len(digests))
                              for j in range(i + 1, len(digests))
                              if digests[i] != digests[j]), (0, 1))
        a = json.loads(outs[ai_bi[0]].read_text())
        b = json.loads(outs[ai_bi[1]].read_text())
        diffs = _summarize_diff(a, b)
        print(f"FAIL: outputs differ across hash seeds", file=sys.stderr)
        if diffs:
            print(f"Divergent fields (seed {HASH_SEEDS[ai_bi[0]]} vs "
                  f"seed {HASH_SEEDS[ai_bi[1]]}):", file=sys.stderr)
            for line in diffs[:30]:
                print(line, file=sys.stderr)
        # Preserve the failing outputs for inspection
        keep = Path(tempfile.mkdtemp(prefix="determinism_test_fail_"))
        for o in outs:
            shutil.copy(o, keep / o.name)
        print(f"  failing outputs preserved in {keep}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
