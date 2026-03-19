from pydantic import BaseModel
from ..intelligence.extract_entities import ClinicalEntities
from ..intelligence.speaker_identifier import SpeakerRoles
from ..model import WhisperXSegment


class JobResult(BaseModel):
    entities: ClinicalEntities
    speaker_roles: SpeakerRoles
    segments: list[WhisperXSegment]
