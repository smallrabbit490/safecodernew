#!/bin/bash

# Security-Aware Code Generation Runner
# This script runs the security-aware code generation workflow on SecEvalPlus benchmark

# Default configuration

#  gemini-3-pro-preview  gpt-5  deepseek-chat  qwen3-235b-a22b
MODEL_NAME="${MODEL_NAME:-qwen3-235b-a22b}"
# NewSecEvalPlus  SecEvalBase
DATA_PATH="${DATA_PATH:-NewSecEvalPlus/NewSecEvalPlus.json}"

MODE="security_aware"
SETTING="security_aware_agent"
MAX_REPAIR_ATTEMPTS="${MAX_REPAIR_ATTEMPTS:-2}"
NUM_WORKERS="${NUM_WORKERS:-8}"
TEMPERATURE="${TEMPERATURE:-0.0}"
MAX_TOKENS="${MAX_TOKENS:-8192}"
TOP_P="${TOP_P:-1.0}"

SAVE_PATH="${SAVE_PATH:-}"
SECURITY_MODE="${SECURITY_MODE:-problem}"  # "single", "all", "repair", or "problem"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-5}"  # seconds to sleep after each instance
RUN_ID="${RUN_ID:-problem_v1}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --model_name)
            MODEL_NAME="$2"
            shift 2
            ;;
        --max_repair_attempts)
            MAX_REPAIR_ATTEMPTS="$2"
            shift 2
            ;;
        --num_workers)
            NUM_WORKERS="$2"
            shift 2
            ;;
        --temperature)
            TEMPERATURE="$2"
            shift 2
            ;;
        --max_tokens)
            MAX_TOKENS="$2"
            shift 2
            ;;
        --top_p)
            TOP_P="$2"
            shift 2
            ;;
        --data_path)
            DATA_PATH="$2"
            shift 2
            ;;
        --save_path)
            SAVE_PATH="$2"
            shift 2
            ;;
        --security_mode)
            SECURITY_MODE="$2"
            shift 2
            ;;
        --sleep_interval)
            SLEEP_INTERVAL="$2"
            shift 2
            ;;
        --run_id)
            RUN_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Security-Aware Code Generation"
echo "=========================================="
echo "Model: $MODEL_NAME"
echo "Mode: $MODE"
echo "Setting: $SETTING"
echo "Security Mode: $SECURITY_MODE"
echo "Run ID: $RUN_ID"
echo "Max Repair Attempts: $MAX_REPAIR_ATTEMPTS"
echo "Num Workers: $NUM_WORKERS"
echo "Temperature: $TEMPERATURE"
echo "Max Tokens: $MAX_TOKENS"
echo "Top P: $TOP_P"
echo "Data Path: $DATA_PATH"
echo "Save Path: ${SAVE_PATH:-auto}"
echo "Sleep Interval: ${SLEEP_INTERVAL}s"
echo "=========================================="

# Change to RACE directory
cd "$(dirname "$0")"

DATA_DIR=$(dirname "$DATA_PATH")
SOURCE_TEST_DIR="$DATA_DIR/Test"
TEMP_DIR="$(pwd)/Temp"
DEST_TEST_DIR="$TEMP_DIR/Test"

if [ -d "$SOURCE_TEST_DIR" ]; then
    echo "Creating temporary directory: $TEMP_DIR"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    echo "Copying test data from $SOURCE_TEST_DIR to $DEST_TEST_DIR ..."
    cp -r "$SOURCE_TEST_DIR" "$DEST_TEST_DIR"
    echo "Test data copied successfully."
else
    echo "Warning: Source test directory not found: $SOURCE_TEST_DIR"
    echo "Creating empty temporary directory: $TEMP_DIR"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
fi

# Cleanup function to remove temp directory and all artifacts after execution
cleanup() {
    echo ""
    echo "Cleaning up temporary directory and test artifacts..."
    rm -rf "$TEMP_DIR"
    echo "Cleanup completed."
}

# Register cleanup function to run on script exit (success or failure)
trap cleanup EXIT

# Build command
CMD="python main_streamsave.py \
    --model_name $MODEL_NAME \
    --mode $MODE \
    --setting $SETTING \
    --max_repair_attempts $MAX_REPAIR_ATTEMPTS \
    --num_workers $NUM_WORKERS \
    --temperature $TEMPERATURE \
    --max_tokens $MAX_TOKENS \
    --top_p $TOP_P \
    --data_path $DATA_PATH \
    --security_mode $SECURITY_MODE \
    --sleep_interval $SLEEP_INTERVAL \
    --run_id $RUN_ID"

if [ -n "$SAVE_PATH" ]; then
    CMD="$CMD --save_path $SAVE_PATH"
fi

echo "Running: $CMD"
echo ""

eval $CMD
