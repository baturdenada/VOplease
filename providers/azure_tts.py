"""Azure Speech provider implemented with the public REST API."""

from __future__ import annotations

import asyncio
from html import escape
from typing import List

import requests

from providers.base import TTSProvider, Voice, TTSOptions, register_provider


@register_provider
class AzureTTSProvider(TTSProvider):
    name = "azure"
    display_name = "Azure Speech"
    requires_api_key = True
    supports_speed = True
    default_voice = "en-US-AriaNeural"
    supported_formats = ["mp3", "wav", "ogg"]
    max_text_length = 10000

    AZURE_VOICES = [
        Voice("en-US-AriaNeural", "Aria (US English)", "en-US", "female"),
        Voice("en-US-DavisNeural", "Davis (US English)", "en-US", "male"),
        Voice("en-US-GuyNeural", "Guy (US English)", "en-US", "male"),
        Voice("en-US-JennyNeural", "Jenny (US English)", "en-US", "female"),
        Voice("en-US-NancyNeural", "Nancy (US English)", "en-US", "female"),
        Voice("en-US-TonyNeural", "Tony (US English)", "en-US", "male"),
        Voice("en-GB-LibbyNeural", "Libby (UK English)", "en-GB", "female"),
        Voice("en-GB-RyanNeural", "Ryan (UK English)", "en-GB", "male"),
        Voice("en-AU-NatashaNeural", "Natasha (AU English)", "en-AU", "female"),
        Voice("es-ES-ElviraNeural", "Elvira (ES Spanish)", "es-ES", "female"),
        Voice("fr-FR-DeniseNeural", "Denise (FR French)", "fr-FR", "female"),
        Voice("de-DE-KatjaNeural", "Katja (DE German)", "de-DE", "female"),
        Voice("it-IT-ElsaNeural", "Elsa (IT Italian)", "it-IT", "female"),
        Voice("pt-BR-FranciscaNeural", "Francisca (BR Portuguese)", "pt-BR", "female"),
        Voice("ja-JP-NanamiNeural", "Nanami (JP Japanese)", "ja-JP", "female"),
        Voice("ko-KR-SunHiNeural", "SunHi (KR Korean)", "ko-KR", "female"),
        Voice("zh-CN-XiaoxiaoNeural", "Xiaoxiao (CN Chinese)", "zh-CN", "female"),
    ]

    def __init__(self, api_key: str = "", region: str = "eastus", **kwargs):
        super().__init__(api_key, **kwargs)
        self.region = region or "eastus"

    async def get_voices(self) -> List[Voice]:
        return self.AZURE_VOICES

    async def synthesize(self, options: TTSOptions) -> bytes:
        if not self.api_key:
            raise ValueError("Azure Speech API key is not configured")

        output_formats = {
            "mp3": "audio-24khz-48kbitrate-mono-mp3",
            "wav": "riff-24khz-16bit-mono-pcm",
            "ogg": "ogg-24khz-16bit-mono-opus",
        }
        rate = max(0.5, min(2.0, float(options.speed)))
        pitch = max(-20.0, min(20.0, float(options.pitch)))
        volume = max(0.0, min(2.0, float(options.volume)))
        language = options.voice_id[:5] if len(options.voice_id) >= 5 else "en-US"
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="{escape(language)}"><voice name="{escape(options.voice_id)}">'
            f'<prosody rate="{rate:.2f}" pitch="{pitch:+.1f}st" '
            f'volume="{volume:.2f}">{escape(options.text)}</prosody>'
            '</voice></speak>'
        )

        def request_audio() -> bytes:
            response = requests.post(
                f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                headers={
                    "Ocp-Apim-Subscription-Key": self.api_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": output_formats.get(
                        options.output_format, output_formats["mp3"]
                    ),
                    "User-Agent": "VOplease",
                },
                data=ssml.encode("utf-8"),
                timeout=120,
            )
            if not response.ok:
                detail = response.text.strip()[:500]
                raise RuntimeError(f"Azure TTS error {response.status_code}: {detail}")
            return response.content

        return await asyncio.to_thread(request_audio)
