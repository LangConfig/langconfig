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

# Lazy-loaded model singleton
_model = None
_model_size = None


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
    delete_after: bool = True,
) -> str:
    """
    Transcribe an audio file to text using local Whisper.

    Args:
        file_path: Path to the audio file (wav, mp3, m4a, webm, etc.)
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        language: Language code or None for auto-detect
        delete_after: If True, delete the source audio file after transcription.
            Defaults to True so workflow-uploaded audio doesn't persist on disk.

    Returns:
        Full transcript text with timestamps.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model = _get_model(model_size)

    try:
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

        return transcript

    finally:
        # Delete source audio — no raw audio retained after transcription
        if delete_after and path.exists():
            try:
                path.unlink()
                logger.info(f"Deleted source audio file: {path}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file {path}: {e}")


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
        # Run in thread to avoid blocking the event loop during transcription
        transcript = await asyncio.to_thread(
            transcribe_audio_file, file_path, model_size, language
        )

        if not transcript.strip():
            return "No speech detected in the audio file."

        return transcript

    except FileNotFoundError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return f"Error transcribing audio: {e}"
