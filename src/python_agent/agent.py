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
    ParsePythonSkill,
    PythonExecutionSkill,
    PythonErrorCorrectionSkill,
    GeneralSkill,
    DirectToUserSkill,
)
from python_agent.controller import LLMInstructController
from python_agent.evaluator import BasicEvaluatorWithSource
from python_agent.llm_fallback import LLMFallback


class AgentApp:
    def __init__(self, work_dir="./python_agent"):
        self.work_dir = work_dir
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

        self.state_history = []

    def load_prompts(self):
        # Load prompts and prompt templates

        self.code_generation_system_message = toml.load(
            f"{self.work_dir}/prompts/python_code_generation.toml"
        )["system"]["prompt"]

        self.code_generation_prompt_template = Template(
            toml.load(f"{self.work_dir}/prompts/python_code_generation.toml")["main"][
                "prompt_template"
            ]
        )

        self.code_correction_system_message = toml.load(
            f"{self.work_dir}/prompts/python_error_correction.toml"
        )["system"]["prompt"]

        self.code_correction_prompt_template = Template(
            toml.load(f"{self.work_dir}/prompts/python_error_correction.toml")["main"][
                "prompt_template"
            ]
        )

        self.general_system_message = toml.load(
            f"{self.work_dir}/prompts/general.toml"
        )["system"]["prompt"]

        self.general_prompt_template = Template(
            toml.load(f"{self.work_dir}/prompts/general.toml")["main"][
                "prompt_template"
            ]
        )

    def init_skills(self):
        """
        Optionally define the code_header.
        """
        code_header = ""

        """
        Code generation.
        """
        self.code_generation_skill = PythonCodeGenerationSkill(
            self.llm,
            system_prompt=self.code_generation_system_message,
            main_prompt_template=self.code_generation_prompt_template,
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
            main_prompt_template=self.general_prompt_template,
        )

        """
        A skill that the Controller can use to just send a message to the user with no additional LLM calls.
        """
        self.direct_to_user_skill = DirectToUserSkill()

    def init_chains(self):
        self.code_generation_chain = Chain(
            name="code_generation_chain",
            description="Generate or edit Python code. If you intend to edit existing code, give an instruction to edit EXISTING CODE.",
            runners=[
                self.code_generation_skill,
                self.parse_python_skill,
            ],
        )

        self.code_execution_chain = Chain(
            name="code_execution_chain",
            description="Execute the script. Use this when the user wants to run the code.",
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
            description="Answer general questions and handle general requests using natural language. Use this when you want to generate a natural language question or response for the user.",
            runners=[self.general_skill],
        )

        self.direct_to_user_chain = Chain(
            name="direct_to_user",
            description="Send a message directly to the user. Use this chain when you're able to respond to the user direclty. Use the 'instructions' part of your response to send a helpful message directly to the user.",
            runners=[self.direct_to_user_skill],
        )

    def init_controller(self):
        self.controller = LLMInstructController(
            llm=self.llm,
            top_k_execution_plan=1,
            hints=[
                # "If the user is asking a question, you should almost always select 'general' to answer it, unless the question is very clearly asking for code to be generated.",
                # "If you're not completely sure how best to help the user, use the 'general' chain to ask for more input.",
                # "Try to be convertional with the user. If they are asking for specific code changes, use the 'code_generation_skill', but if the user is asking any other kind of question, please answer it using the 'general' chain."
                "When you use the 'direct_to_user' chain, use the 'instructions' part of your response to communicate naturally with the user. You're not actually giving instructions, but using that part of the response to have a dialogue."
            ],
        )

    def init_evaluator(self):
        self.evaluator = BasicEvaluatorWithSource()

    def init_agent(self):
        self.agent = Agent(
            controller=self.controller,
            chains=[
                self.code_generation_chain,
                self.code_execution_chain,
                self.error_correction_chain,
                self.general_chain,
                # self.direct_to_user_chain,
            ],
            evaluator=self.evaluator,
        )

    def revert_code(self):
        if len(self.state_history) > 1:
            code = self.state_history.pop()["code"]
            self.context.chatHistory.add_agent_message(
                message="I've reverted the code as per your request.",
            )
            return code
        elif len(self.state_history) > 0:
            self.state_history.pop()
            self.context.chatHistory.add_agent_message(
                message="I've reverted the code as per your request.",
            )
            return "No code to display."
        else:
            self.context.chatHistory.add_agent_message(
                message="Sorry, I couldn't revert the code any further.",
            )
            return "No code to display."

    def interact(self, message, budget=600):
        self.context.chatHistory.add_user_message(message)
        state_pre = self.agent.controller._state.copy()
        result = self.agent.execute(context=self.context, budget=Budget(budget))
        if self.agent.controller._state["code"] != state_pre["code"]:
            self.state_history.append(state_pre)
        last_message = result.messages[-1].message
        self.context.chatHistory.add_agent_message(
            last_message.message, last_message.data
        )
