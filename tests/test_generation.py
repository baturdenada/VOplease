"""Live smoke test for VOplease providers. Uses the locally saved Gemini key."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.manager import config
from providers.base import TTSOptions
from providers.edge_tts import EdgeTTSProvider
from providers.gemini_tts import GeminiTTSProvider, _convert_audio


OUTPUT = ROOT / "test-output"


async def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    api_key = config.get_api_key("gemini")
    if not api_key:
        raise RuntimeError("No saved Gemini API key was found")

    gemini = GeminiTTSProvider(api_key=api_key)
    voices = await gemini.get_voices()
    if len(voices) < 20:
        raise RuntimeError(f"Expected live/fallback Gemini voices, got {len(voices)}")
    voice_id = next((voice.id for voice in voices if voice.id.lower() == "kore"), voices[0].id)

    wav_data = await gemini.synthesize(
        TTSOptions(
            text="VOplease is ready. Gemini text to speech is working correctly.",
            voice_id=voice_id,
            speed=1.0,
            pitch=0.0,
            volume=1.0,
            output_format="wav",
        )
    )
    if not wav_data.startswith(b"RIFF"):
        raise RuntimeError("Gemini output is not a valid RIFF WAV file")
    (OUTPUT / "gemini-test.wav").write_bytes(wav_data)

    mp3_data = _convert_audio(wav_data, "mp3", 1.0)
    if len(mp3_data) < 1_000:
        raise RuntimeError("Converted Gemini MP3 is unexpectedly small")
    (OUTPUT / "gemini-test.mp3").write_bytes(mp3_data)

    edge = EdgeTTSProvider()
    edge_data = await edge.synthesize(
        TTSOptions(
            text="VOplease Edge text to speech is working correctly.",
            voice_id="en-US-AriaNeural",
            output_format="mp3",
        )
    )
    if len(edge_data) < 1_000:
        raise RuntimeError("Edge MP3 is unexpectedly small")
    (OUTPUT / "edge-test.mp3").write_bytes(edge_data)

    print(f"Gemini voices: {len(voices)}")
    print(f"Gemini voice tested: {voice_id}")
    print(f"Gemini WAV bytes: {len(wav_data)}")
    print(f"Gemini MP3 bytes: {len(mp3_data)}")
    print(f"Edge MP3 bytes: {len(edge_data)}")


if __name__ == "__main__":
    asyncio.run(main())
