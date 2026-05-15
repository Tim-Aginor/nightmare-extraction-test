#!/usr/bin/env bash
set -euo pipefail

# Nightmare Extraction Test - Parallel Runner
#
# Same workflow as run_benchmark.sh but fans out extractions per-provider.
# Models in the same cohort that share a provider run sequentially within
# a single lane (respects per-org rate limits); lanes for different
# providers run concurrently (no shared rate limit).
#
# Wall clock = max(per-provider lane time) instead of sum. For the Phase 4
# HIGH+XHIGH sweep (10 model+effort combos) this collapses ~10-13h
# sequential → ~4-5h parallel.
#
# Usage (from a workspace with ground_truth/ and results/):
#   path/to/run_benchmark_parallel.sh                   # default = "blog"
#   path/to/run_benchmark_parallel.sh reasoning_high    # cohort
#   path/to/run_benchmark_parallel.sh reasoning_high reasoning_xhigh
#   path/to/run_benchmark_parallel.sh gpt54 gpt55 opus47   # explicit names
#   path/to/run_benchmark_parallel.sh --score-only      # skip extraction
#
# Per-model logs land in ./logs/<timestamp>/<model>.log

PUBLIC_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -x "$PWD/.venv/bin/python" ]]; then
    PYTHON="$PWD/.venv/bin/python"
elif [[ -x "$PUBLIC_DIR/.venv/bin/python" ]]; then
    PYTHON="$PUBLIC_DIR/.venv/bin/python"
elif [[ -x "$PUBLIC_DIR/../.venv/bin/python" ]]; then
    PYTHON="$PUBLIC_DIR/../.venv/bin/python"
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
        for key in "${missing[@]}"; do echo "  export $key=..."; done
        echo ""
    fi
}

score_all() {
    echo "=== Scoring Results ==="
    for model_dir in results/*/; do
        if [[ -d "$model_dir" ]]; then
            local model
            model=$(basename "$model_dir")
            echo "  Scoring: $model"
            "$PYTHON" "$PUBLIC_DIR/scripts/score.py" \
                --ground-truth ground_truth/ \
                --extractions "results/$model/" \
                --output "results/$model/scores.json"
        fi
    done
}

run_post_extraction() {
    score_all
    # Build hallucination model list from whatever's actually in results/.
    # Avoids hardcoded model lists drifting out of sync with new cohorts.
    local hall_models=()
    for d in results/*/; do
        [[ -d "$d" ]] || continue
        local name
        name=$(basename "$d")
        [[ "$name" == "analysis" ]] && continue
        hall_models+=("$name")
    done

    echo ""
    echo "=== Hallucination Analysis ==="
    "$PYTHON" "$PUBLIC_DIR/scripts/hallucination_analysis.py" \
        --models "${hall_models[@]}" \
        --ground-truth ground_truth/ \
        --results results/ \
        --output results/hallucination_report.json

    echo ""
    echo "=== Generating Report ==="
    "$PYTHON" "$PUBLIC_DIR/scripts/generate_report.py" --results results/ --output report.md
}

# --score-only short-circuit (mirrors run_benchmark.sh)
if [[ "${1:-}" == "--score-only" ]]; then
    run_post_extraction
    echo ""
    echo "Report: report.md"
    exit 0
fi

# Default cohort if no args
ARGS=("$@")
[[ ${#ARGS[@]} -eq 0 ]] && ARGS=("blog")

check_keys

if [[ ! -d ground_truth ]] || [[ -z "$(ls -A ground_truth/*.json 2>/dev/null)" ]]; then
    echo "ERROR: No ground truth found in \$PWD/ground_truth/."
    exit 1
fi

# Resolve cohort/model args into per-provider lane lines
LANES=$("$PYTHON" "$PUBLIC_DIR/scripts/expand_cohort.py" "${ARGS[@]}")
if [[ -z "$LANES" ]]; then
    echo "ERROR: no models resolved from args: ${ARGS[*]}"
    exit 1
fi

LOGDIR="logs/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"

echo "=== Phase: extraction ==="
echo "Logs:  $LOGDIR"
echo "Lanes:"
echo "$LANES" | sed 's/^/  /'
echo ""

# Spawn one subshell per provider lane.
# Within a lane, models run sequentially (avoids per-org rate limit hits).
PIDS=()
LANE_NAMES=()
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    provider=$(echo "$line" | awk '{print $1}')
    models=$(echo "$line" | cut -d' ' -f2-)
    LANE_NAMES+=("$provider")

    (
        for model in $models; do
            echo "[$(date +%H:%M:%S)] [$provider] starting $model" \
                | tee -a "$LOGDIR/_dispatch.log"
            if "$PYTHON" "$PUBLIC_DIR/scripts/run_extraction.py" \
                    --model "$model" \
                    > "$LOGDIR/${model}.log" 2>&1; then
                echo "[$(date +%H:%M:%S)] [$provider] $model OK" \
                    | tee -a "$LOGDIR/_dispatch.log"
            else
                rc=$?
                echo "[$(date +%H:%M:%S)] [$provider] $model FAIL exit=$rc" \
                    | tee -a "$LOGDIR/_dispatch.log"
            fi
        done
    ) &
    PIDS+=($!)
done <<< "$LANES"

# Wait for all lanes; track failures
fails=0
for i in "${!PIDS[@]}"; do
    if ! wait "${PIDS[$i]}"; then
        fails=$((fails + 1))
        echo "lane '${LANE_NAMES[$i]}' (pid ${PIDS[$i]}) had a failure"
    fi
done

if [[ $fails -gt 0 ]]; then
    echo ""
    echo "WARN: $fails lane(s) reported a failure - inspect $LOGDIR/"
fi

echo ""
echo "=== Phase: scoring + hallucination + report ==="
run_post_extraction

echo ""
echo "============================================================"
echo "DONE"
echo "  Results: results/"
echo "  Report:  report.md"
echo "  Logs:    $LOGDIR/"
echo "============================================================"
