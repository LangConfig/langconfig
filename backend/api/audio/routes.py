"""
Audio Transcription API
========================

Upload audio files for local speech-to-text transcription.
Audio is processed in-memory and never persisted to disk in raw form.
"""

import logging
import tempfile
import os
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["audio"])

SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac",
    ".mp4", ".mpeg", ".mpga", ".oga", ".opus",
}


class TranscriptionResponse(BaseModel):
    transcript: str
    duration_seconds: float
    language: str
    segment_count: int


class AudioUploadResponse(BaseModel):
    file_path: str          # Temp file path that workflow nodes can read + delete
    file_name: str
    size_bytes: int


@router.post("/upload", response_model=AudioUploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file for workflow consumption.

    The file is written to a system temp location and the path is returned.
    The workflow's audio_transcribe tool reads and deletes it. The raw
    transcript is NEVER returned to the UI — it lives only inside the
    workflow until it's been run through the PII gate.
    """
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported audio format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    content = await file.read()

    # Persist to temp — workflow tool deletes it after transcription
    with tempfile.NamedTemporaryFile(
        suffix=ext, delete=False, prefix="lc_audio_"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    logger.info(f"Audio uploaded: {file.filename} ({len(content)} bytes) -> {tmp_path}")

    return AudioUploadResponse(
        file_path=tmp_path,
        file_name=file.filename or os.path.basename(tmp_path),
        size_bytes=len(content),
    )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model_size: str = Form("base"),
    language: str = Form("en"),
):
    """
    Transcribe an uploaded audio file using local Whisper.

    Audio is written to a temporary file for processing, then immediately
    deleted. No raw audio is persisted.

    Args:
        file: Audio file (wav, mp3, m4a, webm, ogg, flac, etc.)
        model_size: Whisper model (tiny, base, small, medium, large-v3)
        language: Language code (default: en)

    Returns:
        TranscriptionResponse with full transcript and metadata.
    """
    # Validate model size
    if model_size not in ("tiny", "base", "small", "medium", "large-v3"):
        raise HTTPException(400, "model_size must be: tiny, base, small, medium, or large-v3")

    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported audio format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    try:
        from tools.audio_transcribe_tool import transcribe_audio_file
    except ImportError:
        raise HTTPException(
            503,
            "Audio transcription not available. Install faster-whisper."
        )

    # Write to temp file, transcribe, then delete immediately
    tmp_path = None
    try:
        content = await file.read()
        logger.info(f"Received audio file: {file.filename} ({len(content)} bytes)")

        # Write to temp file (Whisper needs a file path)
        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, prefix="lc_audio_"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Transcribe (single pass — collects transcript + metadata)
        import asyncio
        from tools.audio_transcribe_tool import _get_model

        def _transcribe_with_metadata(path, model_sz, lang):
            model = _get_model(model_sz)
            segments, info = model.transcribe(
                path, language=lang, beam_size=5, vad_filter=True,
            )
            lines = []
            seg_count = 0
            for seg in segments:
                mins = int(seg.start // 60)
                secs = int(seg.start % 60)
                lines.append(f"[{mins:02d}:{secs:02d}] {seg.text.strip()}")
                seg_count += 1
            return "\n".join(lines), info.duration, info.language, seg_count

        transcript, duration, lang_detected, seg_count = await asyncio.to_thread(
            _transcribe_with_metadata, tmp_path, model_size, language
        )

        return TranscriptionResponse(
            transcript=transcript,
            duration_seconds=round(duration, 1),
            language=lang_detected,
            segment_count=seg_count,
        )

    except FileNotFoundError:
        raise HTTPException(400, "Audio file could not be processed")
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(500, f"Transcription failed: {e}")
    finally:
        # Always delete the temp file — no raw audio on disk
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.info(f"Temp audio file deleted: {tmp_path}")
