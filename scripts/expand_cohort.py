#!/usr/bin/env python3
"""Expand a cohort name (or list of model names) into per-provider lanes.

Output format (one line per provider that has any models):
    openai gpt54_high gpt55_high
    anthropic opus47_high sonnet_high
    google gemini_pro_high

Cohorts mirror run_extraction.py's --model special values. Bash callers
parse the output to build parallel lanes.

Usage:
    expand_cohort.py blog
    expand_cohort.py reasoning_high
    expand_cohort.py gpt54 gpt55 opus47
    expand_cohort.py blog gpt54_high     # mix cohort + explicit
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "configs" / "models.yaml"


def cohort_models(args: list[str], config: dict) -> list[str]:
    all_models = {m["name"]: m for m in config["models"]}
    level_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "XHIGH": 3}
    cohorts = {
        "blog":            [m for m in config["models"] if m.get("blog_order")],
        "reasoning":       [m for m in config["models"] if m.get("reasoning")],
        "reasoning_high":  [m for m in config["models"] if m.get("reasoning_level") == "HIGH"],
        "reasoning_xhigh": [m for m in config["models"] if m.get("reasoning_level") == "XHIGH"],
        "all":             [m for m in config["models"] if not m.get("extended")],
        "gpt54_sweep":     sorted([m for m in config["models"] if m.get("gpt_sweep")],
                                  key=lambda m: level_order.get(m.get("reasoning_level"), 99)),
    }

    selected: list[str] = []
    for a in args:
        if a in cohorts:
            selected.extend(m["name"] for m in cohorts[a])
        elif a in all_models:
            selected.append(a)
        else:
            print(f"unknown model/cohort: {a}", file=sys.stderr)
            sys.exit(2)

    seen: set[str] = set()
    return [m for m in selected if not (m in seen or seen.add(m))]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: expand_cohort.py <cohort_or_model> [...]", file=sys.stderr)
        return 2
    config = yaml.safe_load(CONFIG.read_text())
    all_models = {m["name"]: m for m in config["models"]}
    ordered = cohort_models(sys.argv[1:], config)

    lanes: dict[str, list[str]] = {}
    for name in ordered:
        provider = all_models[name]["provider"]
        lanes.setdefault(provider, []).append(name)

    for provider in ("openai", "anthropic", "google"):
        if provider in lanes:
            print(f"{provider} {' '.join(lanes[provider])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
