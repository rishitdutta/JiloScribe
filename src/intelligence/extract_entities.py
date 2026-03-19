from typing import Literal

from pydantic import BaseModel, Field

from ..model import WhisperXSegmentIdentifiedSpeaker
from .llm import model


PROMPTS: dict[str, str] = {
    "system": (
        "You are a medical entity extraction engine.\n"
        "Your task is to extract clinically relevant entities from a doctor-patient conversation.\n\n"
        "Rules:\n"
        "- Use ONLY information explicitly present in the conversation.\n"
        "- Do NOT infer or hallucinate any diagnosis, medication, dosage, age, or condition.\n"
        "- Preserve the original wording when possible.\n"
        "- Conversation may contain mixed languages; extract from all languages.\n"
        "- WhisperX may fail to label some speakers; these will appear as 'UNKNOWN'.\n"
        "- You MUST still use these segments if they contain useful clinical information.\n"
        "- Do NOT assume UNKNOWN is doctor or patient unless context clearly indicates.\n"
        "- If some fields are missing, return null for those specific fields.\n"
        "- Output MUST always be valid JSON matching the schema.\n"
    ),
    "input": ("CONVERSATION:\n{conversation}"),
    "schema": (
        "Return valid JSON exactly in this format:\n"
        "{"
        "entities: {"
        "patient: {name: string | null, age: string | null, sex: 'male'|'female'|'other'|null, identifiers: [string] | null} | null, "
        "encounter: {chief_complaint: string | null, reason_for_visit: string | null, encounter_type: string | null, notes: string | null} | null, "
        "observations: [{name: string, value: string | null, unit: string | null, interpretation: string | null, evidence: [string] | null}] | null, "
        "conditions: [{name: string, status: string | null, severity: string | null, onset: string | null, evidence: [string] | null}] | null, "
        "medication_requests: [{medication: string, dose: string | null, route: string | null, frequency: string | null, duration: string | null, indication: string | null, evidence: [string] | null}] | null"
        "}"
        "}"
    ),
}


class PatientEntity(BaseModel):
    name: str | None = Field(
        default=None, description="Patient name if explicitly stated"
    )
    age: str | None = Field(
        default=None, description="Patient age if explicitly stated"
    )
    sex: Literal["male", "female", "other"] | None = Field(
        default=None, description="Patient sex if explicitly stated"
    )
    identifiers: list[str] | None = Field(
        default=None,
        description="Any explicit identifiers mentioned, such as phone number, UHID, OPD number, or hospital ID",
    )


class EncounterEntity(BaseModel):
    chief_complaint: str | None = Field(
        default=None, description="Main complaint or presenting problem"
    )
    reason_for_visit: str | None = Field(
        default=None, description="Reason the patient came for consultation"
    )
    encounter_type: str | None = Field(
        default=None,
        description="Visit type such as OPD, follow-up, emergency, teleconsult",
    )
    notes: str | None = Field(
        default=None, description="Any other encounter-level note explicitly present"
    )


class ObservationEntity(BaseModel):
    name: str = Field(
        description="Observation name, e.g. blood pressure, temperature, HbA1c"
    )
    value: str | None = Field(default=None, description="Observed value if present")
    unit: str | None = Field(default=None, description="Unit if present")
    interpretation: str | None = Field(
        default=None, description="Interpretation such as high, low, normal, severe"
    )
    evidence: list[str] | None = Field(
        default=None, description="Short supporting phrases from the conversation"
    )


class ConditionEntity(BaseModel):
    name: str = Field(
        description="Condition or symptom name, e.g. fever, diabetes, cough"
    )
    status: str | None = Field(
        default=None,
        description="Status such as suspected, confirmed, resolved, chronic, acute",
    )
    severity: str | None = Field(
        default=None,
        description="Severity if explicitly stated, e.g. mild, moderate, severe",
    )
    onset: str | None = Field(
        default=None, description="Onset or duration if explicitly stated"
    )
    evidence: list[str] | None = Field(
        default=None, description="Short supporting phrases from the conversation"
    )


class MedicationRequestEntity(BaseModel):
    medication: str = Field(description="Medication name")
    dose: str | None = Field(default=None, description="Dose if explicitly stated")
    route: str | None = Field(default=None, description="Route if explicitly stated")
    frequency: str | None = Field(
        default=None, description="Frequency if explicitly stated"
    )
    duration: str | None = Field(
        default=None, description="Duration if explicitly stated"
    )
    indication: str | None = Field(
        default=None, description="Reason for prescribing if explicitly stated"
    )
    evidence: list[str] | None = Field(
        default=None, description="Short supporting phrases from the conversation"
    )


class ClinicalEntities(BaseModel):
    patient: PatientEntity | None = Field(
        default=None, description="Extracted patient information if available"
    )
    encounter: EncounterEntity | None = Field(
        default=None, description="Extracted encounter-level details if available"
    )
    observations: list[ObservationEntity] | None = Field(
        default=None, description="Observed measurements, vitals, or lab values"
    )
    conditions: list[ConditionEntity] | None = Field(
        default=None, description="Symptoms, diagnoses, or clinical problems"
    )
    medication_requests: list[MedicationRequestEntity] | None = Field(
        default=None, description="Medications mentioned or prescribed"
    )


class EntityExtractionResult(BaseModel):
    entities: ClinicalEntities = Field(
        description="Structured clinical entities extracted from the conversation"
    )


structured_llm = model.with_structured_output(
    EntityExtractionResult,
    method="json_schema",
)


def build_conversation(segments: list[WhisperXSegmentIdentifiedSpeaker]) -> str:
    return "\n".join(
        f"{seg.speaker if seg.speaker is not None else 'UNKNOWN'}: {seg.text.strip()}"
        for seg in segments
        if seg.text.strip()
    )


def extract_entities(
    segments: list[WhisperXSegmentIdentifiedSpeaker],
) -> EntityExtractionResult:
    conversation = build_conversation(segments)

    prompt: str = PROMPTS["system"] + "\n\n"
    prompt += PROMPTS["input"].replace("{conversation}", conversation) + "\n\n"
    prompt += PROMPTS["schema"]

    return structured_llm.invoke(prompt)  # pyright: ignore[reportReturnType]
