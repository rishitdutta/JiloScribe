from ..model import WhisperXSegment, WhisperXSegmentIdentifiedSpeaker
from .llm import model
from typing import Literal
from pydantic import BaseModel, Field


PROMPTS: dict[str, str] = {
    "system": (
        "You are a medical conversation analyzer.\n"
        "Your task is to identify which speaker is the doctor and which is the patient.\n\n"
        "Rules:\n"
        "- Doctor typically asks questions, diagnoses, or gives advice.\n"
        "- Patient describes symptoms, answers questions, or expresses concerns.\n"
        "- Be consistent across the conversation.\n"
        "- If the conversation is too short or ambiguous, return null.\n"
        "- Output ONLY valid JSON matching the schema.\n"
    ),
    "input": ("CONVERSATION:\n{conversation}"),
    "schema": (
        "Return valid JSON exactly in this format:\n"
        "{roles: [{speaker: 'SPEAKER_00'|'SPEAKER_01', role: 'doctor'|'patient'}] | null}"
    ),
}


class SpeakerRole(BaseModel):
    speaker: Literal["SPEAKER_00", "SPEAKER_01"] = Field(
        description="Speaker identifier, e.g., SPEAKER_00"
    )
    role: Literal["doctor", "patient"] = Field(
        description="Either 'doctor' or 'patient'"
    )


class SpeakerRoles(BaseModel):
    roles: list[SpeakerRole] | None = Field(
        description=(
            "Mapping of speakers to roles.\n"
            "Return null if there is not enough information to confidently determine roles."
        )
    )


structured_llm = model.with_structured_output(
    SpeakerRoles,
    method="json_schema",
)


def build_conversation(segments: list[WhisperXSegment]) -> str:
    return "\n".join(
        f"{seg.speaker}: {seg.text.strip()}"
        for seg in segments
        if seg.speaker is not None
    )


def classify_speakers(segments: list[WhisperXSegment]) -> SpeakerRoles:
    filtered_segments = [seg for seg in segments if seg.speaker is not None]
    if len(filtered_segments) < 10:
        return SpeakerRoles(roles=None)

    conversation = build_conversation(filtered_segments)

    prompt: str = PROMPTS["system"] + "\n\n"
    prompt += PROMPTS["input"].replace("{conversation}", conversation) + "\n\n"
    prompt += PROMPTS["schema"]
    return structured_llm.invoke(prompt)  # pyright: ignore[reportReturnType]


def speaker_identifier(
    segments: list[WhisperXSegment],
) -> list[WhisperXSegmentIdentifiedSpeaker]:
    # Try classification
    roles = classify_speakers(segments[:20])  # first 20
    if roles.roles is None:
        print("Retrying with more context...")
        roles = classify_speakers(segments[:40])
    if roles.roles is None:
        print("Retrying with more context...")
        roles = classify_speakers(segments[:60])
    if roles.roles is None:
        raise RuntimeError("Failed to classify speakers")
    
    mapping: dict[Literal["SPEAKER_00", "SPEAKER_01"], Literal["doctor", "patient"]] = {
        r.speaker: r.role for r in roles.roles
    }
    return [
        WhisperXSegmentIdentifiedSpeaker(
            text=segment.text,
            start=segment.start,
            end=segment.end,
            avg_logprob=segment.avg_logprob,
            speaker=mapping[segment.speaker] if segment.speaker is not None else None,
        )
        for segment in segments
    ]
