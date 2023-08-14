from council.llm import AzureLLM
from council.runners import Budget
from council.contexts import AgentContext, ChatHistory
from council.agents import Agent
from council.chains import Chain
from council.llm.openai_llm import OpenAILLM

import dotenv

dotenv.load_dotenv()

from string import Template
import toml
import logging
import os

logging.getLogger("council")

from python_agent.skills import (
    PythonCodeGenerationSkill,
    PythonCodeEditorSkill,
    ParsePythonSkill,
    PythonExecutionSkill,
    PythonErrorCorrectionSkill,
    GeneralSkill,
)
from python_agent.controller import LLMInstructController
from python_agent.evaluator import BasicEvaluatorWithSource
from python_agent.llm_fallback import LLMFallback

work_dir = "./python_agent"


class AgentApp:
    def __init__(self):
        self.context = AgentContext(chat_history=ChatHistory())
        self.llm = LLMFallback(
            OpenAILLM.from_env(), AzureLLM.from_env(), retry_before_fallback=1
        )
        self.load_prompts()
        self.init_skills()
        self.init_chains()
        self.init_controller()
        self.init_evaluator()
        self.init_agent()

    def load_prompts(self):
        # Load prompts and prompt templates

        self.code_generation_system_message = toml.load(
            f"{work_dir}/prompts/python_code_generation.toml"
        )["system"]["prompt"]

        self.code_generation_prompt_template = Template(
            toml.load(f"{work_dir}/prompts/python_code_generation.toml")["main"][
                "prompt_template"
            ]
        )

        self.code_editor_system_message = toml.load(
            f"{work_dir}/prompts/python_code_editor.toml"
        )["system"]["prompt"]

        self.code_editor_prompt_template = Template(
            toml.load(f"{work_dir}/prompts/python_code_editor.toml")["main"][
                "prompt_template"
            ]
        )

        self.code_correction_system_message = toml.load(
            f"{work_dir}/prompts/python_error_correction.toml"
        )["system"]["prompt"]

        self.code_correction_prompt_template = Template(
            toml.load(f"{work_dir}/prompts/python_error_correction.toml")["main"][
                "prompt_template"
            ]
        )

        self.general_system_message = toml.load(f"{work_dir}/prompts/general.toml")[
            "system"
        ]["prompt"]

        self.general_prompt_template = Template(
            toml.load(f"{work_dir}/prompts/general.toml")["main"][
                "prompt_template"
            ]
        )

    def init_skills(self):
        """
        Optionally define the code_header.
        """
        code_header = """```python
        import pandas as pd
        import numpy as np
        ```"""

        """
        Initial code generation.
        """
        self.code_generation_skill = PythonCodeGenerationSkill(
            self.llm,
            system_prompt=self.code_generation_system_message,
            main_prompt_template=self.code_generation_prompt_template,
            code_header=code_header,
        )

        """
        Python code editing skill.
        """
        self.code_editing_skill = PythonCodeEditorSkill(
            self.llm,
            system_prompt=self.code_editor_system_message,
            main_prompt_template=self.code_editor_prompt_template,
            code_header=code_header,
        )

        """
        Validate/parse Python code block - could easily be generalized to regex pattern matching skill.
        """
        self.parse_python_skill = ParsePythonSkill()

        """
        Execute Python code locally in host environment - UNSAFE.
        """
        self.python_execution_skill = PythonExecutionSkill(
            self.llm,
            python_bin_dir=os.environ["PYTHON_BIN_DIR"],
        )

        """
        Python error correction skill.
        """
        self.error_correction_skill = PythonErrorCorrectionSkill(
            self.llm,
            system_prompt=self.code_correction_system_message,
            main_prompt_template=self.code_correction_prompt_template,
            code_header=code_header,
        )

        """
        A general skill for handling other things. This is LLMSkill customized with controller "iteration" support.
        """
        self.general_skill = GeneralSkill(
            self.llm,
            system_prompt=self.general_system_message,
            main_prompt_template=self.general_prompt_template
        )

    def init_chains(self):
        self.code_generation_chain = Chain(
            name="code_generation_chain",
            description="Generate a new Python script. Use this chain when the user wants to write a new Python script.",
            runners=[
                self.code_generation_skill,
                self.parse_python_skill,
            ],
        )

        self.code_editing_chain = Chain(
            name="code_editing_chain",
            description="Edit an existing Python script. Use this when the user wants to make changes to the existing Python code.",
            runners=[
                self.code_editing_skill,
                self.parse_python_skill,
            ],
        )

        self.code_execution_chain = Chain(
            name="code_execution_chain",
            description="Execute the script. Use this when the user just wants to run the code (without edits).",
            runners=[
                self.parse_python_skill,
                self.python_execution_skill,
            ],
        )

        self.error_correction_chain = Chain(
            name="error_correction_chain",
            description="Resolve errors in a Python script. Use this chain when there is an error message present in the 'stderr' field, or when the user is asking to correct or fix an error.",
            runners=[self.error_correction_skill, self.parse_python_skill],
        )

        self.general_chain = Chain(
            name="general",
            description="Answer general questions without the use of any specialized skills. Use this when the user needs the answer to a question that doesn't require any coding.",
            runners=[self.general_skill],
        )

    def init_controller(self):
        self.controller = LLMInstructController(
            llm=self.llm,
            top_k_execution_plan=1,
            hints=[],
        )

    def init_evaluator(self):
        self.evaluator = BasicEvaluatorWithSource()

    def init_agent(self):
        self.agent = Agent(
            controller=self.controller,
            chains=[
                self.code_generation_chain,
                self.code_editing_chain,
                self.code_execution_chain,
                self.error_correction_chain,
                self.general_chain,
            ],
            evaluator=self.evaluator,
        )

    def interact(self, message, budget=600):
        self.context.chatHistory.add_user_message(message)
        result = self.agent.execute(context=self.context, budget=Budget(budget))
        last_message = result.messages[-1].message
        self.context.chatHistory.add_agent_message(
            last_message.message, last_message.data
        )
