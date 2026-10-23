from elevenlabs import ElevenLabs, VoiceSettings
from typing import List
from providers.base import TTSProvider, Voice, TTSOptions, register_provider

@register_provider
class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    display_name = "ElevenLabs"
    requires_api_key = True
    supports_speed = True
    default_voice = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    supported_formats = ["mp3", "wav"]
    max_text_length = 5000
    
    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = ElevenLabs(api_key=api_key) if api_key else None
        self._voices_cache = []
    
    async def get_voices(self) -> List[Voice]:
        if not self.client:
            # Return default voices as fallback when no API key is set
            return [
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
        
        try:
            voices_response = self.client.voices.get_all()
            voices = []
            for v in voices_response.voices:
                voices.append(Voice(
                    id=v.voice_id,
                    name=v.name,
                    language=v.labels.get("language", "en") if v.labels else "en",
                    gender=v.labels.get("gender", "neutral") if v.labels else "neutral",
                    preview_url=v.preview_url if v.preview_url else ""
                ))
            return voices
        except Exception as e:
            print(f"Error fetching ElevenLabs voices: {e}")
            # Return some default voices as fallback
            return [
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
    
    async def synthesize(self, options: TTSOptions) -> bytes:
        if not self.client:
            raise ValueError("ElevenLabs API key not configured")
        
        # Map speed to stability/similarity settings
        # ElevenLabs uses stability (0-1) and similarity_boost (0-1)
        # Speed is controlled differently - we'll use the voice settings
        voice_settings = VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True
        )
        
        audio = self.client.text_to_speech.convert(
            voice_id=options.voice_id,
            text=options.text,
            model_id="eleven_multilingual_v2",
            voice_settings=voice_settings,
            output_format="mp3_44100_128" if options.output_format == "mp3" else "pcm_16000"
        )
        
        # The response is a generator, collect all chunks
        audio_data = b""
        for chunk in audio:
            audio_data += chunk
        
        return audio_data