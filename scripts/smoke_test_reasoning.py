#!/usr/bin/env python3
"""Smoke test for reasoning-enabled extraction variants.

Before scaling to 1184 calls, verify that each provider's API actually
accepts the reasoning/thinking parameters we plan to pass. This runs
ONE document through six configurations:

    - gpt54_high, gpt54_xhigh
    - opus47_high, opus47_xhigh
    - gemini_pro_high, gemini_pro_xhigh

(Sonnet is skipped - it shares plumbing with Opus on the Anthropic side.)

Output:
    - PASS / FAIL per config with the error message on failure
    - Token usage preview per successful call (for cost sanity-check)

Usage:
    export OPENAI_API_KEY=...
    export ANTHROPIC_API_KEY=...
    export GOOGLE_API_KEY=...
    python scripts/smoke_test_reasoning.py

    # Or run a subset:
    python scripts/smoke_test_reasoning.py --provider openai
    python scripts/smoke_test_reasoning.py --provider anthropic
    python scripts/smoke_test_reasoning.py --provider google
"""

import argparse
import os
import sys
import time
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = SCRIPT_DIR.parent
REPO_ROOT = PUBLIC_DIR.parent

# Pull the four extract_* functions from the main runner.
sys.path.insert(0, str(SCRIPT_DIR))
from run_extraction import (  # noqa: E402
    extract_openai,
    extract_anthropic,
    extract_google,
)


def load_smoke_config() -> tuple[Path, str, str]:
    """Pick a public sample PDF + prompt for the smoke test."""
    # Use a public N1 doc so this runs for anyone cloning the repo.
    candidates = [
        PUBLIC_DIR / "examples" / "baseline_N1" / "N1_easy_70001" / "source" / "documents" / "acord_125_70001.pdf",
        PUBLIC_DIR / "packets" / "N1_easy" / "doc_70001" / "documents" / "acord_125_70001.pdf",
        REPO_ROOT / "packets" / "public" / "N1_easy" / "doc_70001" / "documents" / "acord_125_70001.pdf",
    ]
    sample_doc = next((c for c in candidates if c.exists()), None)
    if sample_doc is None:
        raise FileNotFoundError(
            "Could not find a sample PDF for smoke test. Looked in "
            "public/examples/baseline_N1/, public/packets/N1_easy/, and "
            "packets/public/N1_easy/."
        )

    prompt_file = PUBLIC_DIR / "prompts" / "acord_form_extraction.md"
    prompt = prompt_file.read_text()
    return sample_doc, "acord_125", prompt


def run_one(label: str, fn, doc_path: Path, doc_type: str, prompt: str,
            model: str, reasoning: dict) -> dict:
    """Run a single extraction and return a status dict."""
    print(f"\n[{label}] calling {model} with reasoning={reasoning} ...", flush=True)
    start = time.time()
    try:
        parsed, in_tok, out_tok = fn(doc_path, doc_type, model, prompt, reasoning)
        elapsed = time.time() - start
        ok = isinstance(parsed, dict) and not parsed.get("error")
        print(f"  -> {'PASS' if ok else 'PARTIAL'} | in={in_tok} out={out_tok} | {elapsed:.1f}s")
        if not ok:
            print(f"  WARN: extraction returned non-dict or error key: {str(parsed)[:200]}")
        return {"label": label, "ok": ok, "in_tok": in_tok, "out_tok": out_tok,
                "elapsed_s": elapsed, "error": None}
    except Exception as e:
        elapsed = time.time() - start
        print(f"  -> FAIL | {type(e).__name__}: {str(e)[:300]}")
        return {"label": label, "ok": False, "in_tok": 0, "out_tok": 0,
                "elapsed_s": elapsed, "error": f"{type(e).__name__}: {e}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["openai", "anthropic", "google", "all"],
                        default="all", help="Which provider(s) to smoke-test")
    args = parser.parse_args()

    doc_path, doc_type, prompt = load_smoke_config()
    print(f"Smoke test document: {doc_path}")

    results = []

    if args.provider in ("openai", "all"):
        if not os.environ.get("OPENAI_API_KEY"):
            print("SKIP openai: OPENAI_API_KEY not set")
        else:
            results.append(run_one("gpt54_high", extract_openai, doc_path, doc_type, prompt,
                                   "gpt-5.4", {"effort": "high"}))
            results.append(run_one("gpt54_xhigh", extract_openai, doc_path, doc_type, prompt,
                                   "gpt-5.4", {"effort": "xhigh"}))

    if args.provider in ("anthropic", "all"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("SKIP anthropic: ANTHROPIC_API_KEY not set")
        else:
            results.append(run_one("opus47_high", extract_anthropic, doc_path, doc_type, prompt,
                                   "claude-opus-4-7", {"effort": "high"}))
            results.append(run_one("opus47_xhigh", extract_anthropic, doc_path, doc_type, prompt,
                                   "claude-opus-4-7", {"effort": "xhigh"}))

    if args.provider in ("google", "all"):
        if not os.environ.get("GOOGLE_API_KEY"):
            print("SKIP google: GOOGLE_API_KEY not set")
        else:
            results.append(run_one("gemini_pro_high", extract_google, doc_path, doc_type, prompt,
                                   "gemini-3.1-pro-preview", {"thinking_level": "HIGH"}))
            results.append(run_one("gemini_pro_xhigh", extract_google, doc_path, doc_type, prompt,
                                   "gemini-3.1-pro-preview", {"thinking_budget": 32000}))

    # Summary
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    ok_count = sum(1 for r in results if r["ok"])
    print(f"{ok_count}/{len(results)} passed\n")
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"  {status}  {r['label']:<20} in={r['in_tok']:>6} out={r['out_tok']:>6}  {r['elapsed_s']:>5.1f}s")
        if r["error"]:
            print(f"         {r['error'][:200]}")

    # Exit nonzero if any failed - makes this CI-friendly if ever useful.
    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == "__main__":
    main()
