from dataclasses import dataclass


@dataclass
class Message:
    speaker_id: str
    speaker_name: str
    content: str

    def to_display_text(self) -> str:
        return f"{self.speaker_name}: {self.content}"
