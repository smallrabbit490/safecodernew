#!/bin/bash

# Insecure Code Repair Runner
# This script runs the repair mode workflow to fix insecure code from the dataset
# It analyzes the insecure code, identifies functional and security issues, generates tests, and fixes the code

# Default configuration

#  gemini-3-pro-preview  gpt-5  deepseek-chat qwen3-235b-a22b
MODEL_NAME="${MODEL_NAME:-qwen3-235b-a22b}"

# NewSecEvalPlus  SecEvalBase
DATA_PATH="${DATA_PATH:-NewSecEvalPlus/NewSecEvalPlus.json}"

MODE="security_aware"
SETTING="security_aware_agent"

# Repair mode settings
MAX_REPAIR_ATTEMPTS="${MAX_REPAIR_ATTEMPTS:-2}"  # Max attempts to repair failed code
NUM_WORKERS="${NUM_WORKERS:-8}"  # Parallel workers
TEMPERATURE="${TEMPERATURE:-0.0}"  # Sampling temperature
MAX_TOKENS="${MAX_TOKENS:-8192}"  # Max tokens per response
TOP_P="${TOP_P:-1.0}"  # Top-p sampling

SAVE_PATH="${SAVE_PATH:-}"
SECURITY_MODE="repair"  # Fixed to "repair" mode for this script
SLEEP_INTERVAL="${SLEEP_INTERVAL:-5}"  # Seconds to sleep after each task
RUN_ID="${RUN_ID:-repair_v1}"  # Run identifier for organizing outputs

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
        --sleep_interval)
            SLEEP_INTERVAL="$2"
            shift 2
            ;;
        --run_id)
            RUN_ID="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Repair Mode - Fix insecure code from dataset"
            echo ""
            echo "Options:"
            echo "  --model_name MODEL          Model to use (default: deepseek-chat)"
            echo "  --max_repair_attempts N     Max repair attempts (default: 2)"
            echo "  --num_workers N             Number of parallel workers (default: 8)"
            echo "  --temperature T             Sampling temperature (default: 0.0)"
            echo "  --max_tokens N              Max tokens per response (default: 8192)"
            echo "  --top_p P                   Top-p sampling (default: 1.0)"
            echo "  --data_path PATH            Path to dataset JSON (default: NewSecEvalPlus.json)"
            echo "  --save_path PATH            Custom save path (default: auto)"
            echo "  --sleep_interval S          Sleep seconds after each task (default: 5)"
            echo "  --run_id ID                 Run identifier (default: repair_v1)"
            echo "  --help                      Show this help message"
            echo ""
            echo "Example:"
            echo "  $0 --model_name deepseek-chat --run_id my_repair"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Insecure Code Repair Mode"
echo "=========================================="
echo "Model: $MODEL_NAME"
echo "Mode: $MODE"
echo "Setting: $SETTING"
echo "Security Mode: $SECURITY_MODE (Repair Mode)"
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
echo ""
echo "Workflow:"
echo "  1. Analyze insecure code (intended behavior + issues)"
echo "  2. Generate functional & security tests"
echo "  3. Fix the code (functional + security)"
echo "  4. Execute tests"
echo "  5. Repair if needed (up to $MAX_REPAIR_ATTEMPTS attempts)"
echo "=========================================="

# Validate data path exists
if [ ! -f "$DATA_PATH" ]; then
    echo "Error: Data file not found: $DATA_PATH"
    exit 1
fi

# Check if data contains "Insecure Code" field
if ! grep -q '"Insecure Code"' "$DATA_PATH"; then
    echo "Warning: Data file may not contain 'Insecure Code' field"
    echo "Repair mode requires datasets with insecure code examples"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Change to RACE directory
cd "$(dirname "$0")"

# Get the Test directory from data path
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

# Cleanup function to remove temp directory after execution
cleanup() {
    echo ""
    echo "Cleaning up temporary directory and test artifacts..."
    rm -rf "$TEMP_DIR"
    echo "Cleanup completed."
}

# Register cleanup function to run on script exit
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

echo ""
echo "Running: $CMD"
echo ""

eval $CMD

# Check if the run was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Repair mode completed successfully!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "Repair mode failed with errors."
    echo "=========================================="
    exit 1
fi
