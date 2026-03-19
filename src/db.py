import os
import json
from fastapi import UploadFile
from pydantic import BaseModel
from .type import JSON


class DataBase:
    def __init__(self) -> None:
        self.transcribe_audio_dir = os.path.abspath("./db/transcribe/audio")
        self.transcribe_job_dir = os.path.abspath("./db/transcribe/job")
        os.makedirs(self.transcribe_audio_dir, exist_ok=True)
        os.makedirs(self.transcribe_job_dir, exist_ok=True)

    async def transcribe_audio_saver(self, file: UploadFile, name: str) -> str:
        file_path = os.path.join(self.transcribe_audio_dir, name)
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)

        return file_path

    @staticmethod
    def _json_save_helper(data: JSON | BaseModel, file_path: str) -> str:
        with open(file_path, "w") as f:
            if not isinstance(data, BaseModel):
                json.dump(data, f, indent=2)
            else:
                f.write(data.model_dump_json())
        return file_path

    def transcribe_job_saver(self, data: JSON | BaseModel, name: str) -> str:
        return self._json_save_helper(
            data,
            os.path.join(self.transcribe_job_dir, name),
        )

    def transcribe_job_loader(self, name: str) -> JSON:
        file_path = os.path.join(self.transcribe_job_dir, name)
        if not os.path.exists(file_path):
            raise FileNotFoundError("Job not found")
        with open(file_path, "rb") as f:
            return json.load(f)
