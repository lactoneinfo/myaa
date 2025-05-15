from dataclasses import dataclass
from typing import List
from myaa.logic.domain.state import AgentState
from myaa.logic.domain.character import load_character


@dataclass
class LLMPrompt:
    role_instruction: str
    format_instruction: str
    responder_description: str
    dialogue_lines: List[str]  # or even List[Tuple[str, str]] for (speaker, utterance)


class PromptFormatter:
    @staticmethod
    def format(state: AgentState) -> LLMPrompt:
        char = load_character(state.responder_name)

        role_instruction = f"You are an playing the role of '{char.name}'.\n"
        format_instruction = "The reply must be in Japanese.\n"
        responder_description = char.description.strip()

        dialogue_lines = []
        for msg in state.context.thread_memory + [state.context.message]:
            line = f"{msg.speaker}: {msg.content}"
            dialogue_lines.append(line)

        return LLMPrompt(
            role_instruction=role_instruction,
            format_instruction=format_instruction,
            responder_description=responder_description,
            dialogue_lines=dialogue_lines,
        )
