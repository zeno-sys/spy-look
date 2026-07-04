from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VadConfig(BaseModel):
    noise_db: float = -35
    min_duration: float = 0.35
    min_silence_sec: float = 0.35
    search_window: int = 60
    sample_rate: int = 16000


class AsrConfig(BaseModel):
    base_url: str = "https://api.siliconflow.cn/v1"
    api_key: str = ""
    model: str = "FunAudioLLM/SenseVoiceSmall"
    max_chunk_sec: int = 240
    max_file_bytes: int = 20971520
    parallel_workers: int = 3
    max_retries: int = 3
    request_timeout_sec: int = 300


class VideoToolsConfig(BaseModel):
    ffmpeg_path: str = ""
    vad: VadConfig = Field(default_factory=VadConfig)
    asr: AsrConfig = Field(default_factory=AsrConfig)


class VideoToolsConfigPatch(BaseModel):
    ffmpeg_path: str | None = None
    vad: VadConfig | None = None
    asr: AsrConfig | None = None


class VoiceToTextUrlRequest(BaseModel):
    url: str
