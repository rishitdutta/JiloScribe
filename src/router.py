import asyncio
from fastapi.middleware.cors import CORSMiddleware
from .job import JobRegistry
from .fastapi import FastAPI
from .routes import live_caption, pipeline
from .db import DataBase
from .config import Settings
from contextlib import asynccontextmanager
from faster_whisper import WhisperModel  # pyright: ignore[reportMissingTypeStubs]
from dataclasses import dataclass
from whisperx import (  # pyright: ignore[reportMissingTypeStubs]
    asr as whisperx_asr,
    alignment as whisperx_alignment,
    diarize as whisperx_diarize,
)
from typing import Any


@dataclass
class GlobalState:
    faster_whisper_model: WhisperModel | None = None
    whisperx_asr_model: whisperx_asr.FasterWhisperPipeline | None = None
    whisperx_alignment_model: (
        tuple[whisperx_alignment.Wav2Vec2ForCTC, dict[str, Any]] | None
    ) = None
    whisperx_diarize_model: whisperx_diarize.DiarizationPipeline | None = None
    settings: Settings | None = None

    def get_settings(self) -> Settings:
        if self.settings is None:
            raise ValueError("please init settings first")
        return self.settings


global_state = GlobalState()


def get_faster_whisper_model():
    global global_state
    if global_state.faster_whisper_model is None:
        global_state.faster_whisper_model = whisperx_asr.WhisperModel(  # WhisperModel(
            "small.en",
            device="cuda",
            compute_type="float16",
            download_root="./models/whisper",
            local_files_only=global_state.get_settings().local_model_only,
        )
    return global_state.faster_whisper_model


def get_whisperx_asr_model(
    whisper_arch: str = "medium.en", model: whisperx_asr.WhisperModel | None = None
):
    global global_state
    if global_state.whisperx_asr_model is None:
        global_state.whisperx_asr_model = whisperx_asr.load_model(  # pyright: ignore[reportUnknownMemberType]
            whisper_arch=whisper_arch,
            model=model,
            device="cuda",
            compute_type="float16",
            download_root="./models/whisper",
            local_files_only=global_state.get_settings().local_model_only,
        )
    return global_state.whisperx_asr_model


def get_whisperx_alignment_model():
    global global_state
    if global_state.whisperx_alignment_model is None:
        global_state.whisperx_alignment_model = whisperx_alignment.load_align_model(  # pyright: ignore[reportUnknownMemberType]
            language_code="en",
            device="cuda",
            model_dir="./models/whisper-align",
            model_cache_only=global_state.get_settings().local_model_only,
        )
    return global_state.whisperx_alignment_model


def get_whisperx_diarize_model():
    global global_state
    if global_state.whisperx_diarize_model is None:
        global_state.whisperx_diarize_model = whisperx_diarize.DiarizationPipeline(
            device="cuda",
            cache_dir="./models/speaker-diarization",
        )
    return global_state.whisperx_diarize_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_state
    if True:  # pre init
        get_faster_whisper_model()
        get_whisperx_asr_model()
        get_whisperx_alignment_model()
        get_whisperx_diarize_model()
    whisperx_job_registry_worker = None
    try:
        app.state.get_faster_whisper_model = get_faster_whisper_model
        app.state.get_whisperx_alignment_model = get_whisperx_alignment_model
        app.state.get_whisperx_asr_model = get_whisperx_asr_model
        app.state.get_whisperx_diarize_model = get_whisperx_diarize_model
        app.state.db = DataBase()
        app.state.settings = global_state.get_settings()
        app.state.whisperx_job_registry = JobRegistry()
        whisperx_job_registry_worker = asyncio.create_task(
            app.state.whisperx_job_registry.worker()
        )
        yield
    finally:
        if whisperx_job_registry_worker is not None:
            app.state.whisperx_job_registry.queue.shutdown()
            try:
                print("shutdowning...")
                await whisperx_job_registry_worker
            finally:
                pass
        global_state.faster_whisper_model = None
        global_state.whisperx_alignment_model = None
        global_state.whisperx_asr_model = None
        global_state.whisperx_diarize_model = None


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(live_caption.router)
app.include_router(pipeline.router)
