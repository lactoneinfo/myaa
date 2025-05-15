from dataclasses import dataclass


@dataclass
class Message:
    speaker: str
    content: str

    def to_display_text(self) -> str:
        return f"{self.speaker}: {self.content}"
