from dataclasses import dataclass
from myaa.domain.character import get_display_name


@dataclass
class Message:
    speaker_id: str
    speaker_name: str
    content: str

    def to_display_text(self) -> str:
        return f"{self.speaker_name}: {self.content}"

    @classmethod
    def from_response(cls, responder_id: str, content: str, **kwargs) -> "Message":
        return cls(
            speaker_id=responder_id,
            speaker_name=get_display_name(responder_id),
            content=content,
            **kwargs,
        )
