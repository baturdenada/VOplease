"""Google Gemini text-to-speech provider.

Uses the Gemini Developer API directly with an API key. It deliberately does
not use Google Cloud Text-to-Speech or Application Default Credentials.
"""

from __future__ import annotations

import asyncio
import base64
import io
import math
import re
import wave
from typing import List

import requests

from providers.base import TTSOptions, TTSProvider, Voice, register_provider


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.8-flash-tts"
CHUNK_SIZE = 6_000

# Used only when the live Voice Library cannot be reached. The live endpoint is
# preferred because it includes language, accent, persona, and extended voices.
FALLBACK_VOICES = [
    Voice("Achernar", "Achernar", "en-US", "female"),
    Voice("Achird", "Achird", "en-US", "male"),
    Voice("Algenib", "Algenib", "en-US", "male"),
    Voice("Algieba", "Algieba", "en-US", "male"),
    Voice("Alnilam", "Alnilam", "en-US", "male"),
    Voice("Aoede", "Aoede", "en-US", "female"),
    Voice("Autonoe", "Autonoe", "en-US", "female"),
    Voice("Callirrhoe", "Callirrhoe", "en-US", "female"),
    Voice("Charon", "Charon", "en-US", "male"),
    Voice("Despina", "Despina", "en-US", "female"),
    Voice("Enceladus", "Enceladus", "en-US", "male"),
    Voice("Erinome", "Erinome", "en-US", "female"),
    Voice("Fenrir", "Fenrir", "en-US", "male"),
    Voice("Gacrux", "Gacrux", "en-US", "female"),
    Voice("Iapetus", "Iapetus", "en-US", "male"),
    Voice("Kore", "Kore", "en-US", "female"),
    Voice("Laomedeia", "Laomedeia", "en-US", "female"),
    Voice("Leda", "Leda", "en-US", "female"),
    Voice("Orus", "Orus", "en-US", "male"),
    Voice("Puck", "Puck", "en-US", "male"),
    Voice("Pulcherrima", "Pulcherrima", "en-US", "female"),
    Voice("Rasalgethi", "Rasalgethi", "en-US", "male"),
    Voice("Sadachbia", "Sadachbia", "en-US", "male"),
    Voice("Sadaltager", "Sadaltager", "en-US", "male"),
    Voice("Schedar", "Schedar", "en-US", "male"),
    Voice("Sulafat", "Sulafat", "en-US", "female"),
    Voice("Umbriel", "Umbriel", "en-US", "male"),
    Voice("Vindemiatrix", "Vindemiatrix", "en-US", "female"),
    Voice("Zephyr", "Zephyr", "en-US", "female"),
    Voice("Zubenelgenubi", "Zubenelgenubi", "en-US", "male"),
]


def _split_text(text: str, limit: int = CHUNK_SIZE) -> list[str]:
    """Split arbitrarily long text without dropping or reordering content."""
    text = text.strip()
    if not text:
        return []

    paragraphs = re.split(r"(\n\s*\n)", text)
    chunks: list[str] = []
    current = ""

    def append_piece(piece: str) -> None:
        nonlocal current
        if len(current) + len(piece) <= limit:
            current += piece
            return
        if current.strip():
            chunks.append(current.strip())
        current = piece

    for paragraph in paragraphs:
        if len(paragraph) <= limit:
            append_piece(paragraph)
            continue

        sentences = re.split(r"(?<=[.!?。！？])\s+", paragraph)
        for sentence in sentences:
            while len(sentence) > limit:
                split_at = sentence.rfind(" ", 0, limit)
                if split_at < limit // 2:
                    split_at = limit
                append_piece(sentence[:split_at])
                sentence = sentence[split_at:].lstrip()
            if sentence:
                append_piece(sentence + " ")

    if current.strip():
        chunks.append(current.strip())
    return chunks


def _style_for(options: TTSOptions) -> str:
    directions: list[str] = []
    if abs(options.speed - 1.0) >= 0.02:
        directions.append(f"Speak at approximately {options.speed:.2f} times normal speed")
    if options.pitch >= 1.0:
        directions.append("use a noticeably higher vocal pitch")
    elif options.pitch <= -1.0:
        directions.append("use a noticeably lower vocal pitch")
    return "; ".join(directions) or "natural, clear narration"


def _extract_audio(payload: dict) -> bytes:
    candidates: list[str] = []
    for step in payload.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for item in step.get("content", []):
            if item.get("type") == "audio" and item.get("data"):
                candidates.append(item["data"])
    if not candidates:
        raise RuntimeError("Gemini returned no audio data")
    return base64.b64decode(candidates[-1])


def _merge_wav(parts: list[bytes]) -> bytes:
    if len(parts) == 1:
        return parts[0]

    output = io.BytesIO()
    format_params = None
    frames: list[bytes] = []
    for index, part in enumerate(parts, start=1):
        try:
            with wave.open(io.BytesIO(part), "rb") as source:
                params = (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                    source.getcompname(),
                )
                if format_params is None:
                    format_params = params
                elif params != format_params:
                    raise RuntimeError("Gemini returned incompatible WAV formats between chunks")
                frames.append(source.readframes(source.getnframes()))
        except wave.Error as exc:
            raise RuntimeError(f"Gemini chunk {index} was not valid WAV audio") from exc

    assert format_params is not None
    with wave.open(output, "wb") as target:
        channels, sample_width, frame_rate, compression, compression_name = format_params
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(frame_rate)
        target.setcomptype(compression, compression_name)
        for frame_data in frames:
            target.writeframes(frame_data)
    return output.getvalue()


def _convert_audio(wav_data: bytes, output_format: str, volume: float) -> bytes:
    output_format = output_format.lower()
    if output_format == "wav" and abs(volume - 1.0) < 0.01:
        return wav_data

    try:
        from pydub import AudioSegment
        import imageio_ffmpeg

        AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        segment = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
        if volume <= 0:
            segment = segment - 120
        elif abs(volume - 1.0) >= 0.01:
            segment = segment + (20.0 * math.log10(volume))
        target = io.BytesIO()
        export_format = "ogg" if output_format == "ogg" else output_format
        segment.export(target, format=export_format)
        return target.getvalue()
    except Exception as exc:
        raise RuntimeError(
            f"Gemini generated WAV audio, but conversion to {output_format.upper()} failed: {exc}"
        ) from exc


@register_provider
class GeminiTTSProvider(TTSProvider):
    name = "gemini"
    display_name = "Google Gemini TTS"
    requires_api_key = True
    supports_speed = True
    supports_pitch = True
    default_voice = "Kore"
    supported_formats = ["mp3", "wav", "ogg"]
    # Long input is handled internally in chunks.
    max_text_length = 10_000_000

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", DEFAULT_MODEL)
        self.timeout = int(kwargs.get("timeout", 180))

    async def get_voices(self) -> List[Voice]:
        if self._voices_cache:
            return self._voices_cache
        if not self.api_key:
            return FALLBACK_VOICES

        def fetch() -> list[Voice]:
            response = requests.get(
                f"{API_ROOT}/voices",
                headers={"x-goog-api-key": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            voices = []
            for item in response.json().get("voices", []):
                voice_id = item.get("id") or item.get("name")
                if not voice_id:
                    continue
                label = item.get("display_name") or item.get("displayName") or voice_id
                persona = item.get("persona")
                if persona:
                    label = f"{label} — {persona}"
                voices.append(
                    Voice(
                        id=voice_id,
                        name=label,
                        language=item.get("language_code", "multi"),
                        gender=item.get("gender", "neutral"),
                    )
                )
            return voices

        try:
            voices = await asyncio.to_thread(fetch)
            self._voices_cache = voices or FALLBACK_VOICES
        except Exception:
            self._voices_cache = FALLBACK_VOICES
        return self._voices_cache

    def _synthesize_chunk(self, text: str, voice_id: str, style: str) -> bytes:
        payload = {
            "model": self.model,
            "input": [
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [
                                {"type": "speech_metadata", "style": style}
                            ],
                        }
                    ],
                }
            ],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice_id}]},
        }
        response = requests.post(
            f"{API_ROOT}/interactions",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(f"Gemini TTS failed ({response.status_code}): {detail[:600]}")
        return _extract_audio(response.json())

    async def synthesize(self, options: TTSOptions) -> bytes:
        if not self.api_key:
            raise ValueError("Google Gemini API key is not configured")
        chunks = _split_text(options.text)
        if not chunks:
            raise ValueError("Text is empty")
        style = _style_for(options)
        wav_parts = []
        for chunk in chunks:
            wav_parts.append(
                await asyncio.to_thread(
                    self._synthesize_chunk,
                    chunk,
                    options.voice_id,
                    style,
                )
            )
        merged_wav = _merge_wav(wav_parts)
        return await asyncio.to_thread(
            _convert_audio,
            merged_wav,
            options.output_format,
            options.volume,
        )
