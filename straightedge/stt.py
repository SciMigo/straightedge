from __future__ import annotations

from pathlib import Path


def transcribe_audio(audio_path: Path) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "No STT backend is installed. Install the optional dependency with "
            "`pip install '.[stt]'`, or pass Chinese text directly."
        ) from exc

    model = WhisperModel("small", device="auto", compute_type="auto")
    segments, _info = model.transcribe(str(audio_path), language="zh")
    return "".join(segment.text for segment in segments).strip()
