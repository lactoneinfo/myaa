from dataclasses import dataclass
from typing import List
from myaa.logic.domain.state import AgentState
from myaa.logic.domain.character import load_character
from myaa.config.prompt_defaults import PROMPT_DEFAULTS


@dataclass
class LLMPrompt:
    role_instruction: str
    format_instruction: str
    responder_description: str
    dialogue_lines: List[str]  # or even List[Tuple[str, str]] for (speaker, utterance)


class PromptFormatter:
    @staticmethod
    def format(state: AgentState) -> LLMPrompt:
        char = load_character(state.responder_id)

        role_instruction = PROMPT_DEFAULTS["role_instruction"].format(
            char_name=char.name
        )
        format_instruction = PROMPT_DEFAULTS["format_instruction"]
        responder_description = char.description.strip()

        dialogue_lines = []
        for msg in state.context.thread_memory + [state.context.message]:
            line = f"{msg.speaker_name}: {msg.content}"
            dialogue_lines.append(line)

        return LLMPrompt(
            role_instruction=role_instruction,
            format_instruction=format_instruction,
            responder_description=responder_description,
            dialogue_lines=dialogue_lines,
        )
