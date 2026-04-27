#!/usr/bin/env bash
set -euo pipefail

# Nightmare Extraction Test - Full Run
#
# Data (ground_truth/, results/) is read and written relative to the
# CURRENT WORKING DIRECTORY, so the same script works both for public
# users (who symlink examples/baseline_N1/N1_easy_70001/source/ground_truth.json
# into ./ground_truth/) and for the maintainer running against a full
# private workspace.
#
# Usage (from the directory that contains ground_truth/ and results/):
#   path/to/run_benchmark.sh              # Run all 5 blog models
#   path/to/run_benchmark.sh gpt55        # Run specific model
#   path/to/run_benchmark.sh --score-only # Just score existing results

PUBLIC_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use venv python if present (prefer workspace venv, else public venv)
if [[ -x "$PWD/.venv/bin/python" ]]; then
    PYTHON="$PWD/.venv/bin/python"
elif [[ -x "$PUBLIC_DIR/.venv/bin/python" ]]; then
    PYTHON="$PUBLIC_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

check_keys() {
    local missing=()
    [[ -z "${OPENAI_API_KEY:-}" ]] && missing+=("OPENAI_API_KEY")
    [[ -z "${ANTHROPIC_API_KEY:-}" ]] && missing+=("ANTHROPIC_API_KEY")
    [[ -z "${GOOGLE_API_KEY:-}" ]] && missing+=("GOOGLE_API_KEY")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "WARNING: Missing API keys: ${missing[*]}"
        echo "Some models may fail. Set them with:"
        for key in "${missing[@]}"; do
            echo "  export $key=..."
        done
        echo ""
    fi
}

score_all() {
    echo "=== Scoring Results ==="
    for model_dir in results/*/; do
        if [[ -d "$model_dir" ]]; then
            model=$(basename "$model_dir")
            echo "  Scoring: $model"
            "$PYTHON" "$PUBLIC_DIR/scripts/score.py" \
                --ground-truth ground_truth/ \
                --extractions "results/$model/" \
                --output "results/$model/scores.json"
        fi
    done
}

main() {
    if [[ "${1:-}" == "--score-only" ]]; then
        score_all
        "$PYTHON" "$PUBLIC_DIR/scripts/hallucination_analysis.py" \
            --models gpt55 gpt54 opus47 sonnet gemini_pro \
            --ground-truth ground_truth/ \
            --results results/ \
            --output results/hallucination_report.json
        "$PYTHON" "$PUBLIC_DIR/scripts/generate_report.py" --results results/ --output report.md
        echo ""
        echo "Report: report.md"
        exit 0
    fi

    check_keys

    if [[ ! -d ground_truth ]] || [[ -z "$(ls -A ground_truth/*.json 2>/dev/null)" ]]; then
        echo "ERROR: No ground truth found in \$PWD/ground_truth/."
        echo "Either run from a workspace that already has one, or generate it:"
        echo "  $PYTHON $PUBLIC_DIR/scripts/generate_ground_truth.py \\"
        echo "    --generator-output <path-to-generator-nightmare-output>"
        exit 1
    fi

    echo "=== Running Extractions ==="
    if [[ -n "${1:-}" ]]; then
        "$PYTHON" "$PUBLIC_DIR/scripts/run_extraction.py" --model "$1"
    else
        "$PYTHON" "$PUBLIC_DIR/scripts/run_extraction.py" --model all
    fi

    score_all

    echo ""
    echo "=== Running Hallucination Analysis ==="
    "$PYTHON" "$PUBLIC_DIR/scripts/hallucination_analysis.py" \
        --models gpt55 gpt54 opus47 sonnet gemini_pro \
        --ground-truth ground_truth/ \
        --results results/ \
        --output results/hallucination_report.json

    echo ""
    echo "=== Generating Report ==="
    "$PYTHON" "$PUBLIC_DIR/scripts/generate_report.py" --results results/ --output report.md

    echo ""
    echo "============================================================"
    echo "DONE"
    echo "  Results: results/"
    echo "  Report:  report.md"
    echo "============================================================"
}

main "$@"
