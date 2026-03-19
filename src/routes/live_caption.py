import asyncio
from fastapi.routing import APIRouter
from ..fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import numpy as np
from faster_whisper import WhisperModel as WhisperModel  # pyright: ignore[reportMissingTypeStubs]

router = APIRouter()

type ChunkShape = np.ndarray[tuple[int, int], np.dtype[np.float32]]


def rms_level(samples: ChunkShape) -> float:
    return np.sqrt(np.mean(np.square(samples), axis=None))


async def input_stream_handler(
    ws: WebSocket, audio_queue: asyncio.Queue[ChunkShape]
) -> None:
    try:
        while True:
            chunk = await ws.receive_bytes()
            chunk = np.frombuffer(chunk, dtype=np.float32)
            chunk = chunk.reshape(-1, 1)  # mono
            await audio_queue.put(chunk)
    except WebSocketDisconnect:
        print("[input stream handler] Client disconnected.")
    except Exception as e:
        print("[input stream handler] Unexpected error:", e)
    finally:
        audio_queue.shutdown()


async def caption_handler(
    ws: WebSocket,
    audio_queue: asyncio.Queue[ChunkShape],
    model: WhisperModel,
    rms_threshold: float = 0.01,
    max_chunks: int = 4,
    samplerate: int = 16000,
):
    final_chunks: list[ChunkShape] = []
    chunk_duration: float | None = None  # seconds
    try:
        while True:
            chunk: ChunkShape = await audio_queue.get()
            if rms_level(chunk) > rms_threshold:
                final_chunks.append(chunk)
                chunk_duration = len(chunk) / samplerate
                # total_sec = sum(len(c) for c in final_chunks) / samplerate
                # print(f"Added {len(chunk) / samplerate:.2f}s, total {total_sec:.1f}s")
                if len(final_chunks) <= max_chunks:
                    continue
            if len(final_chunks) == 0:
                continue

            audio_data = np.concatenate(
                final_chunks, axis=0, dtype=np.float32
            ).flatten()  # downcast to f32

            segments, _ = await asyncio.to_thread(
                model.transcribe, # type: ignore
                audio_data,
                beam_size=5,
                vad_filter=True,
            )
            segments = list(segments)
            if len(segments) == 0:
                final_chunks.clear()
                continue
            if len(segments) > 1:
                stable_text = "".join(seg.text for seg in segments[:-1])

                await ws.send_json({"type": "final", "text": stable_text})
                if chunk_duration is None:
                    print("[caption handler] chunk_duration is None")
                    continue
                idx = int(segments[-2].end // chunk_duration)
                final_chunks = final_chunks[idx:]

            partial_text = segments[-1].text
            await ws.send_json({"type": "partial", "text": partial_text})
    except asyncio.QueueShutDown:
        print("[caption handler] Stopped...")
    except Exception as e:
        print("[caption handler] Unexpected error:", e)


@router.websocket("/ws/live_caption")
async def websocket_live_caption(ws: WebSocket):
    model = ws.app.state.get_faster_whisper_model()

    await ws.accept()

    audio_queue: asyncio.Queue[ChunkShape] = asyncio.Queue()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            input_stream_handler(ws, audio_queue),
            name="input stream handler",
        )
        tg.create_task(
            caption_handler(ws, audio_queue, model),
            name="caption handler",
        )
