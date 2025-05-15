import os
from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import LLMPrompt
from myaa.logic.provider.abstract import LLMProvider
from myaa.logic.domain.character import get_display_name

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool


parameters = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
    },
    "required": ["content"],
}

structured_output_hint = "Only respond via the structured_response function.\n"


class GeminiProvider(LLMProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        if not model_name:
            raise ValueError("GEMINI_MODEL is not set")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

        self.tools = [
            Tool(
                function_declarations=[
                    FunctionDeclaration(
                        name="structured_response",
                        description="Structured JSON output",
                        parameters=parameters,
                    )
                ]
            )
        ]

    def _adapt_prompt(self, prompt: LLMPrompt) -> str:
        return "\n".join(
            [
                prompt.role_instruction,
                prompt.format_instruction,
                structured_output_hint,
                f"responder description:\n{prompt.responder_description}\n",
                "Conversation so far:",
                *[f"User: {line}" for line in prompt.dialogue_lines],
            ]
        )

    async def chat(self, messages: LLMPrompt, responder_id: str) -> Message:
        prompt = self._adapt_prompt(messages)

        response = self.model.generate_content(
            contents=prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 512,
            },
            tools=self.tools,
        )

        try:
            function_call = response.candidates[0].content.parts[0].function_call
            args = function_call.args
            content = args["content"]
            responder_name = get_display_name(responder_id)
            if content.startswith(f"{responder_name}:"):
                content = content.split(":", 1)[-1].strip()
        except Exception:
            raise ValueError("Structured output missing or invalid")

        return Message.from_response(responder_id=responder_id, content=content)
