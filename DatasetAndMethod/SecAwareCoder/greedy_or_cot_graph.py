from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_openai import ChatOpenAI
from configuration import CG_Configuration, CT_Configuration
from langchain_core.runnables import RunnableConfig
import logging, os
from prompts import code_generation_prompt, code_translation_prompt, code_generation_cot_prompt, code_translation_cot_prompt
from state import CG_State, CT_State
from utils import setup_openai_api, format_log_message, create_llm_with_reasoning_control

load_dotenv()

def get_logger(name="CodeTransLogger", log_file="logs/CodeTrans.log",
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

logger = get_logger(name="cg_greedy", log_file="logs/cg_greedy.log")

def code_generator(state: CG_State, config: RunnableConfig):
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Starting Code Generation"))
    configurable = CG_Configuration.from_runnable_config(config)
    formatted_prompt = code_generation_prompt.format(
        task_description=state["task"],
        target_language=configurable.target_language
        )
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Generation Prompt:\n{formatted_prompt}"))
    llm = create_llm_with_reasoning_control(
        model_name=configurable.model_name,
        temperature=configurable.temperature,
        max_tokens=configurable.max_tokens,
        top_p=configurable.top_p,
        disable_reasoning=True
    )
    try:
        response = llm.invoke(formatted_prompt).content
    except Exception as e:
        logger.info("Task %s failed with error: %s", state["task_id"], str(e))
        raise e
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Generated Code:\n{response}"))
    return {
        "code": response,
    }

def code_generator_cot(state: CG_State, config: RunnableConfig):
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Starting Code Generation"))
    configurable = CG_Configuration.from_runnable_config(config)
    formatted_prompt = code_generation_cot_prompt.format(
        task_description=state["task"],
        target_language=configurable.target_language
        )
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Generation Prompt:\n{formatted_prompt}"))
    llm = create_llm_with_reasoning_control(
        model_name=configurable.model_name,
        temperature=configurable.temperature,
        max_tokens=configurable.max_tokens,
        top_p=configurable.top_p,
        disable_reasoning=True
    )
    try:
        response = llm.invoke(formatted_prompt).content
    except Exception as e:
        logger.info("Task %s failed with error: %s", state["task_id"], str(e))
        raise e
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Generated Code:\n{response}"))
    return {
        "code": response,
    }

def code_translator(state: CT_State, config: RunnableConfig):
    """Code translation node."""
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Starting Code Translation"))
    configurable = CT_Configuration.from_runnable_config(config)
    formatted_prompt = code_translation_prompt.format(
        source_language=configurable.source_language,
        target_language=configurable.target_language,
        source_code=state["source_code"]
    )
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Translation Prompt:\n{formatted_prompt}"))
    llm = create_llm_with_reasoning_control(
        model_name=configurable.model_name,
        temperature=configurable.temperature,
        max_tokens=configurable.max_tokens,
        top_p=configurable.top_p,
        disable_reasoning=True
    )

    try:
        response = llm.invoke(formatted_prompt).content
    except Exception as e:
        logger.info(f"Task {state['task_id']} failed with error: {e}")
        raise e

    return {
        "code": response,
    }

def code_translator_cot(state: CT_State, config: RunnableConfig):
    """Code translation node."""
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Starting Code Translation"))
    configurable = CT_Configuration.from_runnable_config(config)
    formatted_prompt = code_translation_cot_prompt.format(
        source_language=configurable.source_language,
        target_language=configurable.target_language,
        source_code=state["source_code"]
    )
    logger.debug(format_log_message(f"Task ID: {state['task_id']} - Translation Prompt:\n{formatted_prompt}"))
    llm = create_llm_with_reasoning_control(
        model_name=configurable.model_name,
        temperature=configurable.temperature,
        max_tokens=configurable.max_tokens,
        top_p=configurable.top_p,
        disable_reasoning=True
    )

    try:
        response = llm.invoke(formatted_prompt).content
    except Exception as e:
        logger.info(f"Task {state['task_id']} failed with error: {e}")
        raise e

    return {
        "code": response,
    }


# Create Graph
def build_cg_greedy_workflow():

    code_agent_builder = StateGraph(CG_State, context_schema=RunnableConfig)
    code_agent_builder.add_node("code_generator", code_generator)

    code_agent_builder.add_edge(START, "code_generator")
    code_agent_builder.add_edge("code_generator", END)
    code_generation_workflow = code_agent_builder.compile()
    return code_generation_workflow

def build_cg_cot_workflow():

    code_agent_builder = StateGraph(CG_State, context_schema=RunnableConfig)
    code_agent_builder.add_node("code_generator_cot", code_generator_cot)

    code_agent_builder.add_edge(START, "code_generator_cot")
    code_agent_builder.add_edge("code_generator_cot", END)
    code_generation_workflow = code_agent_builder.compile()
    return code_generation_workflow

def build_ct_greedy_workflow():

    code_agent_builder = StateGraph(CT_State, context_schema=RunnableConfig)
    code_agent_builder.add_node("code_translator", code_translator)

    code_agent_builder.add_edge(START, "code_translator")
    code_agent_builder.add_edge("code_translator", END)
    code_translation_workflow = code_agent_builder.compile()
    return code_translation_workflow

def build_ct_cot_workflow():
    code_agent_builder = StateGraph(CT_State, context_schema=RunnableConfig)
    code_agent_builder.add_node("code_translator_cot", code_translator_cot)
    code_agent_builder.add_edge(START, "code_translator_cot")
    code_agent_builder.add_edge("code_translator_cot", END)
    code_translation_workflow = code_agent_builder.compile()
    return code_translation_workflow