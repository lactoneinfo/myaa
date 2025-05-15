from typing import List, Dict
from myaa.logic.domain.state import AgentState
from myaa.logic.domain.character import load_character


class PromptFormatter:
    @staticmethod
    def format(state: AgentState) -> List[Dict]:
        char = load_character(state.character_name)

        system = {
            "role": "system",
            "content": f"You are {char.name}. {char.description}",
        }

        messages = [system]

        for msg in state.context.thread_memory + [state.context.message]:
            role = "assistant" if msg.speaker == state.character_name else "user"
            messages.append({"role": role, "content": f"{msg.speaker}: {msg.content}"})

        return messages
