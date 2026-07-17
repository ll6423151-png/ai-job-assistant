from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app.core.config import settings
from app.schemas.interview import SpeechRequest
from app.services.local_transcription import LocalTranscriptionError, transcribe_locally


router = APIRouter()


def _openai_client():
    if settings.ai_provider.lower() != "openai" or not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI 语音服务未配置，当前可继续使用浏览器语音能力",
        )
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key)


@router.post("/interview-audio/transcriptions")
async def transcribe_audio(file: UploadFile = File(...)) -> dict[str, str]:
    max_bytes = settings.audio_upload_max_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="音频文件为空")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"音频不能超过 {settings.audio_upload_max_mb} MB")
    allowed = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
    filename = Path(file.filename or "answer.webm").name
    if Path(filename).suffix.lower() not in allowed:
        raise HTTPException(status_code=422, detail="音频格式不受支持")
    if settings.ai_provider.lower() == "openai" and settings.openai_api_key:
        audio = BytesIO(content)
        audio.name = filename
        try:
            result = _openai_client().audio.transcriptions.create(
                model=settings.openai_transcription_model,
                file=audio,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="OpenAI 语音转写暂时不可用") from exc
        text = result.text.strip()
        engine = "openai"
    else:
        try:
            text = transcribe_locally(content, filename)
        except LocalTranscriptionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        engine = f"local:{settings.local_transcription_model}"
    return {"text": text, "engine": engine}


@router.post("/interview-audio/speech")
def synthesize_speech(payload: SpeechRequest) -> Response:
    try:
        result = _openai_client().audio.speech.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=payload.text,
            response_format="mp3",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="语音合成暂时不可用") from exc
    return Response(content=result.content, media_type="audio/mpeg")
