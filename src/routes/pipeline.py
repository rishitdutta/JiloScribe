from fastapi.routing import APIRouter
from ..fastapi import Request
from fastapi import UploadFile, File, Query

# from fastapi.responses import JSONResponse
from uuid import uuid4, UUID
from pydantic import BaseModel, UUID4
from ..job import Job, JobStatus
from ..intelligence.whisperx_transcribe import whisperx_transcribe
from ..intelligence.speaker_identifier import speaker_identifier
from ..intelligence.extract_entities import extract_entities, EntityExtractionResult
from datetime import datetime
from functools import partial


router = APIRouter()


def pipeline_job(audio_file_path: str, req: Request) -> EntityExtractionResult:
    segments = whisperx_transcribe(audio_file_path, req)
    segments = speaker_identifier(segments)
    return extract_entities(segments)


class PipelineJobCreated(BaseModel):
    job_id: UUID4
    status: JobStatus
    created_at: datetime


def job_save_callback(job: Job[..., EntityExtractionResult], req: Request) -> None:
    req.app.state.db.transcribe_job_saver(
        PipelineJobResponse(
            job_id=UUID(job.id),
            status=job.status,
            result=job.result if job.status == JobStatus.DONE else None,
            error=str(job.error) if job.status == JobStatus.FAILED else None,
        ),
        job.id,
    )


@router.post("/pipeline", response_model=PipelineJobCreated)
async def create_pipeline(
    req: Request, file: UploadFile = File(...)
) -> PipelineJobCreated:
    job_registry = req.app.state.whisperx_job_registry

    job_id = uuid4()
    audio_file_path = await req.app.state.db.transcribe_audio_saver(file, str(job_id))
    job = Job(job_id, pipeline_job, audio_file_path, req)
    job.add_callback(callback=partial(job_save_callback, req=req))
    await job_registry.submit(job=job)
    return PipelineJobCreated(
        job_id=job_id, status=job.status, created_at=job.created_at
    )


class PipelineJobResponse(BaseModel):
    job_id: UUID4
    status: JobStatus
    result: None | EntityExtractionResult = None
    error: None | str = None


@router.get("/pipeline/{job_id}", response_model=PipelineJobResponse)
async def get_pipeline_job(
    req: Request, job_id: UUID4, wait: bool = Query(False)
) -> PipelineJobResponse:
    try:
        job = req.app.state.db.transcribe_job_loader(str(job_id))
        return PipelineJobResponse.model_validate(job)
    except FileNotFoundError:
        pass
    job_registry = req.app.state.whisperx_job_registry
    job = job_registry.get(str(job_id))

    if not job:
        return PipelineJobResponse(
            job_id=job_id, status=JobStatus.FAILED, error="Job not found"
        )

    if wait:
        await job.event.wait()

    result = PipelineJobResponse(
        job_id=job_id,
        status=job.status,
        result=job.result if job.status == JobStatus.DONE else None,
        error=str(job.error) if job.status == JobStatus.FAILED else None,
    )
    # if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
    #     req.app.state.db.transcribe_job_saver(result, str(job_id))
    return result
