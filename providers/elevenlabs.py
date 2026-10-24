"""ElevenLabs provider using the public REST API."""

from __future__ import annotations

import asyncio
from typing import List

import requests

from providers.base import TTSOptions, TTSProvider, Voice, register_provider


DEFAULT_VOICES = [
    Voice("21m00Tcm4TlvDq8ikWAM", "Rachel", "en", "female"),
    Voice("AZnzlk1XvdvUeBnXmlld", "Domi", "en", "female"),
    Voice("EXAVITQu4vr4xnSDxMaL", "Bella", "en", "female"),
    Voice("ErXwobaYiN019PkySvjV", "Antoni", "en", "male"),
    Voice("MF3mGyEYCl7XYWbV9V6O", "Elli", "en", "female"),
    Voice("TxGEqnHWrfWFTfGW9XjX", "Josh", "en", "male"),
    Voice("VR6AewLTigWG4xSOukaG", "Arnold", "en", "male"),
    Voice("pNInz6obpgDQGcFmaJgB", "Adam", "en", "male"),
    Voice("yoZ06aMxZJJ28mfd3POQ", "Sam", "en", "male"),
]


@register_provider
class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    display_name = "ElevenLabs"
    requires_api_key = True
    supports_speed = True
    default_voice = "21m00Tcm4TlvDq8ikWAM"
    supported_formats = ["mp3"]
    max_text_length = 5000

    async def get_voices(self) -> List[Voice]:
        if not self.api_key:
            return DEFAULT_VOICES

        def fetch() -> list[Voice]:
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            voices = []
            for item in response.json().get("voices", []):
                labels = item.get("labels") or {}
                voices.append(
                    Voice(
                        id=item["voice_id"],
                        name=item.get("name", item["voice_id"]),
                        language=labels.get("language", "multi"),
                        gender=labels.get("gender", "neutral"),
                        preview_url=item.get("preview_url", ""),
                    )
                )
            return voices or DEFAULT_VOICES

        try:
            return await asyncio.to_thread(fetch)
        except Exception as exc:
            print(f"Error fetching ElevenLabs voices: {exc}")
            return DEFAULT_VOICES

    async def synthesize(self, options: TTSOptions) -> bytes:
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured")

        def request_audio() -> bytes:
            # MP3 is universally supported by ElevenLabs and the built-in player.
            # The dashboard's WAV option is intended primarily for Gemini/Azure.
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{options.voice_id}",
                params={"output_format": "mp3_44100_128"},
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": options.text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                        "speed": max(0.7, min(1.2, float(options.speed))),
                    },
                },
                timeout=180,
            )
            if not response.ok:
                raise RuntimeError(
                    f"ElevenLabs TTS failed ({response.status_code}): {response.text[:500]}"
                )
            return response.content

        return await asyncio.to_thread(request_audio)
