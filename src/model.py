from pydantic import BaseModel
from typing import Literal


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


class SrtSegmentInput(BaseModel):
    id: int
    text: str
    start: float = 0.0
    end: float = 0.0

    def to_srt(self) -> str:
        return (
            f"{self.id}"
            "\n"
            f"{format_timestamp(self.start)} --> "
            f"{format_timestamp(self.end)}"
            "\n"
            f"{self.text.strip()}"
            "\n"
            "\n"
        )


class BaseWhisperXSegment(BaseModel):
    text: str
    start: float = 0.0
    end: float = 0.0
    avg_logprob: float


class WhisperXSegment(BaseWhisperXSegment):
    speaker: None | Literal[
        "SPEAKER_01", "SPEAKER_00"
    ]  # NOTE: maybe some third person but will see that later


class WhisperXSegmentIdentifiedSpeaker(BaseWhisperXSegment):
    speaker: None | Literal["doctor", "patient"]
