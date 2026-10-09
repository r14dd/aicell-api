"""Gemini over plain REST: JSON/text generation, speech to text, text to speech, embeddings."""

import base64
import io
import json
import urllib.request
import wave

from django.conf import settings

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT = 60


class GeminiError(Exception):
    pass


def _post(model, method, body):
    request = urllib.request.Request(
        f"{BASE}/{model}:{method}",
        json.dumps(body).encode(),
        {"x-goog-api-key": settings.GEMINI_API_KEY, "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except Exception as error:
        raise GeminiError(str(error)) from error


def _parts(data):
    return data["candidates"][0]["content"]["parts"]


def _usage(data):
    meta = data.get("usageMetadata", {})
    return meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)


def generate(system, prompt, *, schema=None, json_schema=None):
    """Returns `(text, tokens_in, tokens_out)`; with `schema`, `text` is JSON of that shape."""
    config = {"thinkingConfig": {"thinkingBudget": 0}}
    if schema:
        config |= {"responseMimeType": "application/json", "responseSchema": schema}
    if json_schema:
        config |= {"responseMimeType": "application/json", "responseJsonSchema": json_schema}
    data = _post(
        settings.GEMINI_MODEL,
        "generateContent",
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": config,
        },
    )
    tokens_in, tokens_out = _usage(data)
    return _parts(data)[0]["text"], tokens_in, tokens_out


def transcribe(audio: bytes, mime: str) -> str:
    data = _post(
        settings.GEMINI_STT_MODEL,
        "generateContent",
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Transcribe this speech exactly, in its own language. Output only the transcript."
                        },
                        {
                            "inlineData": {
                                "mimeType": mime,
                                "data": base64.b64encode(audio).decode(),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
        },
    )
    return _parts(data)[0]["text"].strip()


AZ_LETTERS = set("əƏıİöÖüÜşŞçÇğĞ")


def speak(text: str) -> bytes:
    """The text as a 24 kHz mono 16-bit WAV, in Azerbaijani when it has Azerbaijani letters."""
    code = "az-AZ" if AZ_LETTERS & set(text) else "en-US"
    data = _post(
        settings.GEMINI_TTS_MODEL,
        "generateContent",
        {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "languageCode": code,
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": settings.GEMINI_VOICE}},
                },
            },
        },
    )
    pcm = base64.b64decode(_parts(data)[0]["inlineData"]["data"])
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    return out.getvalue()


def embed_query(text: str) -> list[float]:
    data = _post(
        settings.GEMINI_EMBED_MODEL,
        "embedContent",
        {
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
            "outputDimensionality": 768,
        },
    )
    values = data["embedding"]["values"]
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]
