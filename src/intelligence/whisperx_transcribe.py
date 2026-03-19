from ..fastapi import Request
from ..model import WhisperXSegment
from whisperx import (  # pyright: ignore[reportMissingTypeStubs]
    alignment as whisperx_alignment,
    audio as whisperx_audio,
    diarize as whisperx_diarize,
)


def whisperx_transcribe(audio_file_path: str, req: Request) -> list[WhisperXSegment]:
    asr_model = req.app.state.get_whisperx_asr_model()
    align_model, align_metadata = req.app.state.get_whisperx_alignment_model()
    diarize_model = req.app.state.get_whisperx_diarize_model()

    audio = whisperx_audio.load_audio(audio_file_path)
    asr_result = asr_model.transcribe(
        audio,
        batch_size=8,
        language="en",
    )
    align_result = whisperx_alignment.align(  # pyright: ignore[reportUnknownMemberType]
        asr_result["segments"],
        align_model,
        align_metadata,
        audio,
        "cuda",
        return_char_alignments=False,
    )
    diarize_segments = diarize_model(audio)
    final_result = whisperx_diarize.assign_word_speakers(
        diarize_segments,  # pyright: ignore[reportArgumentType]
        align_result,
    )
    result = [
        WhisperXSegment(
            text=segment["text"],
            start=segment["start"],
            end=segment["end"],
            avg_logprob=segment["avg_logprob"],  # pyright: ignore[reportTypedDictNotRequiredAccess]
            speaker=segment.get("speaker", None),  # type: ignore
        )
        for segment in final_result["segments"]
    ]
    return result
