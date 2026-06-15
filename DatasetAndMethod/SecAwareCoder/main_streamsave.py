from security_aware_code_generation_graph import build_security_aware_workflow

from utils import load_jsonl
import logging
from concurrent.futures import as_completed, ThreadPoolExecutor
from tqdm import tqdm
import json, os, fire, threading, time
from datetime import datetime
from langchain_core.runnables import RunnableConfig



# ==========================================================
# Logger setup
# ==========================================================
def get_logger(name="CodeGenLogger", log_file="logs/codegen.log",
               console_level=logging.INFO, file_level=logging.DEBUG):
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(console)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)
    return logger


logger = get_logger()
write_lock = threading.Lock()


def build_workflow_and_inputs(config: dict = None):
    mode = config["mode"]
    setting = config["setting"]
    security_mode = config.get("security_mode", "single")  # Default to "single"

    workflow_map = {
        "security_aware": {
            "security_aware_agent": lambda: build_security_aware_workflow(security_mode=security_mode),
        },
    }

    if mode not in workflow_map or setting not in workflow_map[mode]:
        raise ValueError(f"Unsupported mode '{mode}' or setting '{setting}'")

    workflow = workflow_map[mode][setting]()

    inputs_builder_map = {
        "security_aware": {
            "security_aware_agent": lambda tid, task: {
                "task_id": tid,
                "task": task,
                "insecure_code": task.get("insecure_code", ""),  # For repair mode
            },
        },
    }

    return workflow, inputs_builder_map[mode][setting]

def normalize_result(res, task_id, config_dict):
    mode = config_dict["mode"]
    setting = config_dict["setting"]
    security_mode = config_dict.get("security_mode", "single")

    if mode == "security_aware":
        if setting == "security_aware_agent":
            # Extract token usage statistics
            token_usage = res.get("token_usage", {})

            # Check if this is repair mode based on whether 'analysis' exists in result
            if "analysis" in res and security_mode == "repair":
                # Repair mode result
                return {
                    "task_id": res.get("task_id", task_id),
                    "code": res.get("code", ""),
                    "all_infos": res.get("all_infos", []),
                    "exec_outcome": res.get("exec_outcome", []),
                    "insecure_code": res.get("insecure_code", ""),
                    "analysis": res.get("analysis").model_dump() if res.get("analysis") else {},
                    "generated_tests": {
                        "functional_tests_summary": res.get("generated_tests").functional_tests_summary if res.get("generated_tests") else "",
                        "security_tests_summary": res.get("generated_tests").security_tests_summary if res.get("generated_tests") else "",
                        "test_cases": [tc.model_dump() for tc in res.get("generated_tests").test_cases] if res.get("generated_tests") else [],
                        "test_code": res.get("generated_tests").test_code if res.get("generated_tests") else "",
                    },
                    "max_repair_attempts": res.get("max_repair_attempts", -1),
                    "token_usage": {
                        "prompt_tokens": token_usage.get("prompt_tokens", 0),
                        "completion_tokens": token_usage.get("completion_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                        "cost_usd": round(token_usage.get("cost", 0.0), 6),
                        "calls": token_usage.get("calls", []),
                    },
                }
            elif security_mode == "problem":
                # Problem mode result (no security analysis)
                return {
                    "task_id": res.get("task_id", task_id),
                    "code": res.get("code", ""),
                    "all_infos": res.get("all_infos", []),
                    "exec_outcome": res.get("exec_outcome", []),
                    "generated_tests": {
                        "target_risk": res.get("generated_tests").target_risk if res.get("generated_tests") else "",
                        "test_cases": [tc.model_dump() for tc in res.get("generated_tests").test_cases] if res.get("generated_tests") else [],
                        "test_code": res.get("generated_tests").test_code if res.get("generated_tests") else "",
                    },
                    "max_repair_attempts": res.get("max_repair_attempts", -1),
                    "token_usage": {
                        "prompt_tokens": token_usage.get("prompt_tokens", 0),
                        "completion_tokens": token_usage.get("completion_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                        "cost_usd": round(token_usage.get("cost", 0.0), 6),
                        "calls": token_usage.get("calls", []),
                    },
                }
            else:
                # Original security_aware mode result (single/all modes)
                return {
                    "task_id": res.get("task_id", task_id),
                    "code": res.get("code", ""),
                    "all_infos": res.get("all_infos", []),
                    "exec_outcome": res.get("exec_outcome", []),
                    "security_analysis": res.get("security_analysis").model_dump() if res.get("security_analysis") else {},
                    "current_risk": res.get("current_risk").model_dump() if res.get("current_risk") else {},
                    "generated_tests": {
                        "target_risk": res.get("generated_tests").target_risk if res.get("generated_tests") else "",
                        "test_cases": [tc.model_dump() for tc in res.get("generated_tests").test_cases] if res.get("generated_tests") else [],
                        "test_code": res.get("generated_tests").test_code if res.get("generated_tests") else "",
                    },
                    "max_repair_attempts": res.get("max_repair_attempts", -1),
                    "token_usage": {
                        "prompt_tokens": token_usage.get("prompt_tokens", 0),
                        "completion_tokens": token_usage.get("completion_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                        "cost_usd": round(token_usage.get("cost", 0.0), 6),
                        "calls": token_usage.get("calls", []),
                    },
                }
        else:
            raise ValueError(f"Unsupported setting '{setting}' for mode 'security_aware'")
    else:
        raise ValueError(f"Unsupported mode '{mode}'")


def run_single_task(workflow, input_builder, task_id, task, config_dict, traj_dir=None):
    """
    Run a single task with optional trajectory saving.

    Args:
        workflow: The LangGraph workflow to execute
        input_builder: Function to build inputs from task_id and task
        task_id: The task identifier
        task: The task data
        config_dict: Configuration dictionary
        traj_dir: Directory to save trajectory files (if None, trajectory is not saved)

    Returns:
        The final result from the workflow
    """
    inputs = input_builder(task_id, task)

    # Initialize trajectory record
    trajectory = {
        "task_id": task_id,
        "start_time": datetime.now().isoformat(),
        "config": {k: v for k, v in config_dict.items() if k not in ["save_path"]},  # Exclude save_path
        "input": {
            "task_id": task_id,
            "task": task,
        },
        "steps": [],
        "final_result": None,
        "error": None,
        "end_time": None,
    }

    try:
        # Use stream with "updates" mode to capture each node's output
        # This gives us {node_name: state_update} for each step
        accumulated_state = dict(inputs)

        for step_output in workflow.stream(
            inputs,
            config=RunnableConfig(configurable={**config_dict}, recursion_limit=40),
            stream_mode="updates"  # Get incremental updates from each node
        ):
            # step_output is a dict like {"node_name": {state_updates}}
            for node_name, state_update in step_output.items():
                step_record = {
                    "step_name": node_name,
                    "timestamp": datetime.now().isoformat(),
                    "output": _serialize_step_output(state_update),
                    "error": None,
                }
                trajectory["steps"].append(step_record)
                logger.debug(f"Task {task_id} - Step '{node_name}' completed")

                # Accumulate state updates
                if isinstance(state_update, dict):
                    accumulated_state.update(state_update)

        # The accumulated_state is the complete result
        trajectory["final_result"] = _serialize_step_output(accumulated_state)
        trajectory["end_time"] = datetime.now().isoformat()

        # Save trajectory if traj_dir is provided
        if traj_dir:
            _save_trajectory(trajectory, task_id, traj_dir)

        return accumulated_state

    except Exception as e:
        trajectory["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        trajectory["end_time"] = datetime.now().isoformat()

        # Save trajectory even on error
        if traj_dir:
            _save_trajectory(trajectory, task_id, traj_dir)

        raise


def _serialize_step_output(output):
    """
    Serialize step output to JSON-compatible format.
    Handles Pydantic models, special objects, etc.
    """
    if output is None:
        return None

    if isinstance(output, dict):
        result = {}
        for k, v in output.items():
            result[k] = _serialize_step_output(v)
        return result

    if isinstance(output, list):
        return [_serialize_step_output(item) for item in output]

    if hasattr(output, "model_dump"):
        # Pydantic model
        return output.model_dump()

    if hasattr(output, "__dict__"):
        # Regular object with __dict__
        try:
            return {k: _serialize_step_output(v) for k, v in output.__dict__.items()
                    if not k.startswith("_")}
        except:
            return str(output)

    # Basic types
    if isinstance(output, (str, int, float, bool, type(None))):
        return output

    # Fallback to string representation
    return str(output)


def _save_trajectory(trajectory, task_id, traj_dir):
    """
    Save trajectory to a JSON file.

    Args:
        trajectory: The trajectory dict to save
        task_id: The task identifier (used as filename)
        traj_dir: Directory to save the trajectory file
    """
    os.makedirs(traj_dir, exist_ok=True)

    # Sanitize task_id to be a valid filename
    safe_task_id = str(task_id).replace("/", "_").replace("\\", "_").replace(":", "_")
    traj_file = os.path.join(traj_dir, f"{safe_task_id}.json")

    try:
        with open(traj_file, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, ensure_ascii=False, indent=2)
        logger.debug(f"Trajectory saved: {traj_file}")
    except Exception as e:
        logger.warning(f"Failed to save trajectory for {task_id}: {e}")


def run_multiple_tasks(task_ids, tasks, config_dict):
    save_path = config_dict["save_path"]
    num_workers = config_dict.get("num_workers", 5)
    sleep_interval = config_dict.get("sleep_interval", 0)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    logger.info(f"Saving incremental results to: {save_path}")

    # Create trajectory directory alongside the output file
    traj_dir = os.path.join(os.path.dirname(save_path), "traj")
    os.makedirs(traj_dir, exist_ok=True)
    logger.info(f"Saving trajectory files to: {traj_dir}")

    # Resume
    existing_ids = set()
    if os.path.exists(save_path):
        with open(save_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line).get("task_id"))
                except:
                    pass
        logger.info(f"Found {len(existing_ids)} existing results, will skip them.")

    remaining = [(tid, t) for tid, t in zip(task_ids, tasks) if tid not in existing_ids]
    logger.info(f"{len(remaining)} tasks remaining out of {len(task_ids)} total.")

    logger.info("Waiting for 10 seconds before starting tasks...")
    time.sleep(10)


    if not remaining:
        logger.info("🎉 All tasks already completed.")
        return

    workflow, input_builder = build_workflow_and_inputs(config_dict)

    # Token usage tracking for summary
    total_token_stats = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "tasks_completed": 0,
        "tasks_failed": 0,
    }

    with ThreadPoolExecutor(max_workers=num_workers) as executor, \
         open(save_path, "a", encoding="utf-8") as fout:

        futures = {
            executor.submit(run_single_task, workflow, input_builder, tid, t, config_dict, traj_dir): tid
            for tid, t in remaining
        }

        for future in tqdm(as_completed(futures), total=len(futures)):
            tid = futures[future]

            try:
                res = future.result()
            except Exception as e:
                logger.error(f"Task {tid} failed with exception: {e}")
                total_token_stats["tasks_failed"] += 1
                continue
            record = normalize_result(res, tid, config_dict)

            # Accumulate token usage for summary
            if "token_usage" in record:
                tu = record["token_usage"]
                total_token_stats["total_prompt_tokens"] += tu.get("prompt_tokens", 0)
                total_token_stats["total_completion_tokens"] += tu.get("completion_tokens", 0)
                total_token_stats["total_tokens"] += tu.get("total_tokens", 0)
                total_token_stats["total_cost_usd"] += tu.get("cost_usd", 0.0)
            total_token_stats["tasks_completed"] += 1

            with write_lock:
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                fout.flush()

            # Sleep after processing each instance (if configured)
            if sleep_interval > 0:
                time.sleep(sleep_interval)

    # Print summary statistics
    logger.info("=" * 60)
    logger.info("TOKEN USAGE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Tasks Completed: {total_token_stats['tasks_completed']}")
    logger.info(f"Tasks Failed: {total_token_stats['tasks_failed']}")
    logger.info(f"Total Prompt Tokens: {total_token_stats['total_prompt_tokens']:,}")
    logger.info(f"Total Completion Tokens: {total_token_stats['total_completion_tokens']:,}")
    logger.info(f"Total Tokens: {total_token_stats['total_tokens']:,}")
    logger.info(f"Total Cost (USD): ${total_token_stats['total_cost_usd']:.4f}")
    if total_token_stats['tasks_completed'] > 0:
        avg_cost = total_token_stats['total_cost_usd'] / total_token_stats['tasks_completed']
        avg_tokens = total_token_stats['total_tokens'] / total_token_stats['tasks_completed']
        logger.info(f"Average Cost per Task (USD): ${avg_cost:.6f}")
        logger.info(f"Average Tokens per Task: {avg_tokens:.0f}")
    logger.info("=" * 60)

    # Save summary to file
    summary_path = save_path.replace(".jsonl", "_token_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(total_token_stats, f, indent=2)
    logger.info(f"Token usage summary saved to: {summary_path}")

def main(
    model_name="gpt-4o-mini",
    mode="security_aware",
    setting="security_aware_agent",
    max_repair_attempts=2,
    num_workers=5,
    temperature=0.0,
    max_tokens=2048,
    top_p=1.0,
    data_path="NewSecEvalPlus/NewSecEvalPlus.json",
    save_path=None,
    security_mode="all",  # "single", "all", "repair", or "problem"
    sleep_interval=0,  # seconds to sleep after processing each instance
    run_id="new_prompt",  # run identifier for organizing outputs
):
    config_dict = {
        "model_name": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "mode": mode,
        "setting": setting,
        "max_repair_attempts": max_repair_attempts,
        "num_workers": num_workers,
        "save_path": save_path,
        "security_mode": security_mode,  # "single", "all", or "repair" for security_aware mode
        "sleep_interval": sleep_interval,  # seconds to sleep after each instance
        "run_id": run_id,  # run identifier for organizing outputs
    }
    logger.info(f"Configuration: {config_dict}")

    # Load SecEvalPlus format data (JSON array)
    if data_path.endswith('.json'):
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = load_jsonl(data_path)

    task_ids = [d["ID"] for d in data]
    tasks = []
    for d in data:
        tasks.append({
            "problem_description": d["Problem"],
            "entry_point": d["Entry_Point"],
            "original_tests": d.get("Test", ""),
            "insecure_code": d.get("Insecure Code", ""),
            "secure_code": d.get("Secure Code", ""),
        })

    if save_path is None:
        # Extract dataset name from data_path
        dataset_name = os.path.splitext(os.path.basename(data_path))[0]
        config_dict["save_path"] = (
            f"data/security_aware/{model_name}/{setting}/{run_id}/{dataset_name}/"
            f"security_aware_{run_id}_{dataset_name}_{model_name}_temp{temperature}_maxtokens{max_tokens}_topp{top_p}.jsonl"
        )

    run_multiple_tasks(task_ids, tasks, config_dict)
    logger.info("🎉 Finished all tasks.")


if __name__ == "__main__":
    fire.Fire(main)
