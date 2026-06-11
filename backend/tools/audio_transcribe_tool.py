"""
Audio Transcription Tool (Local STT)
=====================================

Local speech-to-text using faster-whisper (CTranslate2-optimized Whisper).
Runs entirely on-device — audio never leaves the machine.

Models (downloaded on first use):
  - tiny:  ~75MB, fastest, lower accuracy
  - base:  ~150MB, good balance for demos
  - small: ~500MB, better accuracy
  - medium: ~1.5GB, high accuracy
  - large-v3: ~3GB, best accuracy
"""

import logging
import tempfile
import os
from typing import Optional
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Prefix used by backend/api/audio/routes.py when persisting uploads to temp.
# Only files matching this prefix inside the system temp dir may ever be deleted.
UPLOAD_TEMP_PREFIX = "lc_audio_"

# Lazy-loaded model singleton
_model = None
_model_size = None


def _is_deletable_temp_upload(path: Path) -> bool:
    """True only for files the audio upload API wrote to the system temp dir.

    Guards against agent-controlled arbitrary file deletion: a file is only
    eligible for cleanup when its resolved path lives inside
    tempfile.gettempdir() AND its name carries the upload prefix.
    """
    try:
        resolved = path.resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        return (
            resolved.name.startswith(UPLOAD_TEMP_PREFIX)
            and temp_dir in resolved.parents
        )
    except (OSError, ValueError):
        return False


def _get_model(model_size: str = "base"):
    """Get or create the cached WhisperModel instance."""
    global _model, _model_size

    if _model is not None and _model_size == model_size:
        return _model

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed. "
            "Run: pip install faster-whisper"
        )

    logger.info(f"Loading Whisper model '{model_size}' (first load downloads the model)...")
    _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    _model_size = model_size
    logger.info(f"Whisper model '{model_size}' loaded.")
    return _model


def transcribe_audio_file(
    file_path: str,
    model_size: str = "base",
    language: Optional[str] = "en",
    delete_after: bool = False,
) -> str:
    """
    Transcribe an audio file to text using local Whisper.

    Args:
        file_path: Path to the audio file (wav, mp3, m4a, webm, etc.)
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        language: Language code or None for auto-detect
        delete_after: If True, delete the source audio file after a SUCCESSFUL
            transcription — but only when the file is a temp upload created by
            the audio upload API (inside tempfile.gettempdir() with the
            'lc_audio_' prefix). Other files are never deleted.

    Returns:
        Full transcript text with timestamps.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model = _get_model(model_size)

    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=5,
        word_timestamps=False,
        vad_filter=True,  # Skip silence
    )

    lines = []
    for segment in segments:
        mins = int(segment.start // 60)
        secs = int(segment.start % 60)
        timestamp = f"[{mins:02d}:{secs:02d}]"
        lines.append(f"{timestamp} {segment.text.strip()}")

    transcript = "\n".join(lines)

    logger.info(
        f"Transcribed {path.name}: {info.duration:.1f}s audio, "
        f"{len(lines)} segments, language={info.language}"
    )

    # Delete only after a successful transcription (never in finally, so a
    # failed transcription preserves the source), and only for temp uploads.
    if delete_after:
        if _is_deletable_temp_upload(path):
            try:
                path.unlink()
                logger.info(f"Deleted temp upload audio file: {path}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file {path}: {e}")
        else:
            logger.debug(
                f"Skipping deletion of {path}: not a temp upload "
                f"({UPLOAD_TEMP_PREFIX}* in {tempfile.gettempdir()})"
            )

    return transcript


@tool
async def audio_transcribe(
    file_path: str,
    model_size: str = "base",
    language: str = "en",
) -> str:
    """
    Transcribe an audio file to text using local speech-to-text (Whisper).

    Runs entirely on-device — audio never leaves this machine. Supports
    wav, mp3, m4a, webm, ogg, flac, and most common audio formats.

    Never deletes user files. Temp files created by the audio upload API
    (lc_audio_* in the system temp dir) are cleaned up automatically after
    a successful transcription.

    Args:
        file_path: Path to the audio file to transcribe.
        model_size: Whisper model to use. Options:
            - 'tiny': fastest, lower accuracy (~75MB)
            - 'base': good balance for demos (~150MB)
            - 'small': better accuracy (~500MB)
        language: Language code (default: 'en' for English).

    Returns:
        Full transcript with timestamps.
    """
    import asyncio

    if model_size not in ("tiny", "base", "small", "medium", "large-v3"):
        return f"Error: model_size must be one of: tiny, base, small, medium, large-v3"

    try:
        # Run in thread to avoid blocking the event loop during transcription.
        # delete_after=True only ever removes gated temp uploads (lc_audio_*
        # inside tempfile.gettempdir()) so workflow-uploaded audio doesn't
        # persist on disk; all other paths are never deleted.
        transcript = await asyncio.to_thread(
            transcribe_audio_file, file_path, model_size, language, True
        )

        if not transcript.strip():
            return "No speech detected in the audio file."

        return transcript

    except FileNotFoundError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return f"Error transcribing audio: {e}"
