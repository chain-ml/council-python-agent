from council.skills import SkillBase
from council.contexts import ChatMessage, SkillContext
from council.runners import Budget
from council.llm import LLMBase, LLMMessage

from python_agent.code_sandbox import run_code_in_sandbox

import ast
import logging
import re
from string import Template
from typing import List, Dict

logger = logging.getLogger("council")


class PythonCodeGenerationSkill(SkillBase):
    """General Python code generation skill."""

    def __init__(
        self,
        llm: LLMBase,
        system_prompt: str,
        main_prompt_template: Template,
        code_header: str,
    ):
        """Build a new PythonCodeGenerationSkill."""

        super().__init__(name="PythonCodeGenerationSkill")
        self.llm = llm
        self.system_prompt = LLMMessage.system_message(system_prompt)
        self.main_prompt_template = main_prompt_template
        self.code_header = code_header

    def execute(self, context: SkillContext, _budget: Budget) -> ChatMessage:
        """Execute `PythonCodeGenerationSkill`."""

        prompt = self.main_prompt_template.substitute(
            code_header=self.code_header,
            existing_code=context.last_message.data["code"],
            user_message=context.last_user_message.message,
            task=context.last_message.message,
        )

        messages_to_llm = [
            self.system_prompt,
            LLMMessage.assistant_message(prompt),
        ]

        llm_response = self.llm.post_chat_request(messages=messages_to_llm).first_choice

        logger.debug(f"{self.name}, generated code: {llm_response}")

        return ChatMessage.skill(
            source=self.name,
            message="I've edited code for you and placed the result in the 'data' field.",
            data=context.last_message.data | {"code": llm_response},
        )


class ParsePythonSkill(SkillBase):
    def __init__(self):
        super().__init__(name="ParsePythonSkill")

    def execute(self, context: SkillContext, budget: Budget) -> ChatMessage:
        # Get the code
        code = context.last_message.data["code"]

        try:
            ast.parse(code)
            return ChatMessage.skill(
                source=self.name,
                message="The code is ready, do you want to run it?",
                data=context.last_message.data | {"code": code},
            )
        except (SyntaxError, TypeError):
            pass

        pattern = r"```python\s+(.*?)\s+```"
        matches = re.findall(pattern, code, re.DOTALL)
        if matches:
            python_code = None
            for match in matches:
                python_code = match
            message = "The code is ready, do you want to run it?"
            return ChatMessage.skill(
                source=self.name,
                message=message,
                data=context.last_message.data | {"code": python_code},
            )
        else:
            message = "Sorry, something went wrong and the code doesn't parse... Do you want me to try to fix it?"
            return ChatMessage.skill(
                source=self.name,
                message=message,
                data=context.last_message.data | {"code": code},
                is_error=True,
            )


class PythonErrorCorrectionSkill(SkillBase):
    def __init__(
        self,
        llm: LLMBase,
        system_prompt: str,
        main_prompt_template: Template,
        code_header: str,
    ):
        super().__init__(name="PythonErrorCorrectionSkill")
        self.llm = llm
        self.system_prompt = system_prompt
        self.main_prompt_template = main_prompt_template
        self.code_header = code_header

    def execute(
        self, context: SkillContext, budget: Budget) -> ChatMessage:
        """
        Try to correct error(s) in Python code.
        """

        # Get the instructions (which will be the 'message' from the controller)
        task = context.last_message.message

        # Get the code
        code = context.last_message.data["code"]

        # Get the error(s)
        errors = context.last_message.data["stderr"]

        prompt = self.main_prompt_template.substitute(
            task=task,
            existing_code=code,
            code_header=self.code_header,
            errors=errors,
            user_message=context.last_user_message.message,
        )
        logger.debug(f"{self.name}, prompt {prompt}")

        messages_to_llm = [
            LLMMessage.system_message(self.system_prompt),
            LLMMessage.assistant_message(prompt),
        ]

        llm_response = self.llm.post_chat_request(messages=messages_to_llm).first_choice
        logger.debug(f"{self.name}, corrected code: {llm_response}")

        data = context.last_message.data | {
            "code": llm_response,
            "stdout": None,
            "stderr": None,
        }

        return ChatMessage.skill(
            message="I've generated corrected code and placed it in the 'data' field.",
            data=data,
            source=self.name,
            is_error=False,
        )

class PythonExecutionSkill(SkillBase):
    def __init__(
        self,
        llm: LLMBase,
        python_bin_dir: str,
    ):
        super().__init__(name="PythonExecutionSkill")
        self.llm = llm
        self.python_bin_dir = python_bin_dir

    def execute(self, context: SkillContext, budget: Budget) -> ChatMessage:
        """
        Try to execute a Python file, collecting output (or error message) from the standard output.
        """

        # Get the code
        code = context.last_message.data["code"]

        # Run the code and return the resulting message
        return self.execute_code(context.last_message.data, code)

    def execute_code(self, data, code):
        is_code = False
        try:
            ast.parse(code)
            is_code = True
        except SyntaxError:
            pass

        if not is_code:
            pattern = r"```python\s+(.*?)\s+```"
            matches = re.findall(pattern, code, re.DOTALL)
            if matches:
                python_code = None
                for match in matches:
                    python_code = match
                code = python_code
            else:
                message = "Sorry, something went wrong and the code doesn't parse...Do you want me to try to fix it?"
                logger.debug(f"{self.name}, failed to parse code: {code}")
                return ChatMessage.skill(
                    source=self.name,
                    message=message,
                    data=data | {"code": code},
                    is_error=True,
                )

        try:
            # Run the Python file as a subprocess
            exec_result = run_code_in_sandbox(code, self.python_bin_dir)

            data = data | {
                "code": code,
                "returncode": exec_result["returncode"],
                "stdout": exec_result["stdout"],
                "stderr": exec_result["stderr"],
            }
            if exec_result["returncode"] == 0:
                logger.debug(f"{self.name}, executed code: {code}")
                message_to_user = f"The code executed successfully with standard output: {data['stdout'].strip()}"
                if len(message_to_user) < 1:
                    message_to_user = (
                        "Python code executed successfully with no standard output."
                    )
                return ChatMessage.skill(
                    source=self.name, message=message_to_user, data=data, is_error=False
                )
            else:
                logger.debug(f"{self.name}, failed to execute code: {code}")
                return ChatMessage.skill(
                    source=self.name,
                    message=f"Python code execution failed. There was an error: {data['stderr'][:100]}... Do you want me to try to fix it?",
                    data=data,
                    is_error=True,
                )
        except Exception as e:
            data = data | {
                "code": code,
                "returncode": None,
                "stdout": None,
                "stderr": None,
            }
            logger.debug(f"{self.name}, failed to execute code: {data}")
            return ChatMessage.skill(
                source=self.name,
                message=f"Exception while executing Python code:\n{e}",
                data=data,
                is_error=True,
            )


class GeneralSkill(SkillBase):
    """Respond to questions using plain LLM call."""

    def __init__(
        self,
        llm: LLMBase,
        system_prompt: str,
        main_prompt_template: Template
    ):
        """Build a new GeneralSkill."""

        super().__init__(name="GeneralSkill")
        self.llm = llm
        self.system_prompt = LLMMessage.system_message(system_prompt)
        self.main_prompt_template = main_prompt_template

    def execute(self, context: SkillContext, _budget: Budget) -> ChatMessage:
        """Execute `GeneralSkill`."""

        prompt = self.main_prompt_template.substitute(
            controller_state=context.last_message.data,
            controller_instructions=context.last_message.message
        )

        messages_to_llm = [self.system_prompt, LLMMessage.assistant_message(prompt)]

        llm_response = self.llm.post_chat_request(messages=messages_to_llm).first_choice

        logger.debug(f"{self.name}, response: {llm_response}")

        return ChatMessage.skill(
            source=self.name,
            message=llm_response,
            data=context.last_message.data,
        )

class DirectToUserSkill(SkillBase):
    """Just send a message to the user."""

    def __init__(
        self,
    ):
        """Build a new DirectToUserSkill."""

        super().__init__(name="DirectToUserSkill")

    def execute(self, context: SkillContext, _budget: Budget) -> ChatMessage:
        """Execute `DirectToUserSkill`."""

        message = context.last_message.message

        logger.debug(f"{self.name}, response: {message}")

        return ChatMessage.skill(
            source=self.name,
            message=message,
            data=context.last_message.data,
        )