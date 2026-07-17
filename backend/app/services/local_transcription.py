import os
import tempfile
from pathlib import Path
from threading import Lock

from app.core.config import settings
from opencc import OpenCC


class LocalTranscriptionError(RuntimeError):
    pass


_model = None
_model_lock = Lock()
_traditional_to_simplified = OpenCC("t2s")


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel

                _model = WhisperModel(
                    settings.local_transcription_model,
                    device="cpu",
                    compute_type="int8",
                )
            except Exception as exc:
                raise LocalTranscriptionError("本地语音模型加载失败") from exc
    return _model


def transcribe_locally(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}:
        suffix = ".webm"
    path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as audio_file:
            audio_file.write(content)
            path = audio_file.name
        segments, _ = _get_model().transcribe(
            path,
            language="zh",
            beam_size=5,
            vad_filter=True,
        )
        text = _traditional_to_simplified.convert(
            "".join(segment.text for segment in segments).strip()
        )
    except LocalTranscriptionError:
        raise
    except Exception as exc:
        raise LocalTranscriptionError("本地语音转写失败，请检查音频格式") from exc
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    if not text:
        raise LocalTranscriptionError("没有识别到清晰语音，请靠近麦克风后重试")
    return text
