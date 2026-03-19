from typing import TYPE_CHECKING

if not TYPE_CHECKING:
    from fastapi import FastAPI, Request, WebSocket
else:
    from fastapi import (
        Request as _Request,
        FastAPI as _FastAPI,
        WebSocket as _WebSocket,
    )
    from dataclasses import dataclass
    from typing import Callable
    from faster_whisper import WhisperModel as WhisperModel  # pyright: ignore[reportMissingTypeStubs]
    from whisperx import (  # pyright: ignore[reportMissingTypeStubs]
        asr as whisperx_asr,
        alignment as whisperx_alignment,
        diarize as whisperx_diarize,
    )
    from typing import Any
    from .job import JobRegistry
    from .db import DataBase
    from .routes.pipeline_model import JobResult
    from .config import Settings
    @dataclass()
    class State:
        """define all state type here."""

        get_faster_whisper_model: Callable[[], WhisperModel]
        get_whisperx_asr_model: Callable[[], whisperx_asr.FasterWhisperPipeline]
        get_whisperx_alignment_model: Callable[
            [], tuple[whisperx_alignment.Wav2Vec2ForCTC, dict[str, Any]]
        ]
        get_whisperx_diarize_model: Callable[[], whisperx_diarize.DiarizationPipeline]
        db: DataBase
        whisperx_job_registry: JobRegistry[..., JobResult]
        settings: Settings

    class FastAPI(_FastAPI):
        state: State  # pyright: ignore[reportIncompatibleVariableOverride]

    class WebSocket(_WebSocket):
        app: FastAPI  # pyright: ignore[reportIncompatibleMethodOverride]

    class Request(_Request):
        app: FastAPI  # pyright: ignore[reportIncompatibleMethodOverride]


__all__ = ["FastAPI", "Request", "WebSocket"]
