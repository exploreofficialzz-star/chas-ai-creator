"""Voice generation service using TTS models."""

import io
import uuid
from typing import Optional

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)


class VoiceGenerationService:
    """Service for generating voiceovers from text."""
    
    def __init__(self):
        self.model = settings.VOICE_MODEL
        self.storage = StorageService()
        
        # Available voices
        self.voices = {
            "en_male_1": "English Male 1",
            "en_female_1": "English Female 1",
            "en_male_2": "English Male 2",
            "en_female_2": "English Female 2",
        }
    
    async def generate_voiceover(
        self,
        text: str,
        voice_id: str = "en_female_1",
        speed: float = 1.0,
        pitch: float = 1.0,
    ) -> str:
        """Generate voiceover from text."""
        
        try:
            if self.model == "piper":
                audio_data = await self._generate_with_piper(text, voice_id)
            elif self.model == "coqui":
                audio_data = await self._generate_with_coqui(text, voice_id)
            else:
                # Fallback
                audio_data = await self._generate_placeholder_audio(text)
            
            # Upload to storage
            filename = f"audio/{uuid.uuid4()}.mp3"
            audio_url = await self.storage.upload_file(
                file_data=audio_data,
                filename=filename,
                content_type="audio/mpeg",
            )
            
            logger.info("Voiceover generated successfully")
            return audio_url
            
        except Exception as e:
            logger.error("Voice generation failed", error=str(e))
            return await self._get_placeholder_audio_url()
    
    async def _generate_with_piper(
        self,
        text: str,
        voice_id: str,
    ) -> bytes:
        """Generate voice using Piper TTS."""
        
        try:
            from piper import PiperVoice
            
            # Load voice model
            model_path = f"models/piper/{voice_id}.onnx"
            voice = PiperVoice.load(model_path)
            
            # Synthesize
            audio_buffer = io.BytesIO()
            voice.synthesize(text, audio_buffer)
            audio_buffer.seek(0)
            
            return audio_buffer.getvalue()
            
        except ImportError:
            logger.warning("Piper not installed, using fallback")
            return await self._generate_placeholder_audio(text)
    
    async def _generate_with_coqui(
        self,
        text: str,
        voice_id: str,
    ) -> bytes:
        """Generate voice using Coqui TTS."""
        
        try:
            from TTS.api import TTS
            
            # Initialize TTS
            tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
            
            # Generate
            audio_buffer = io.BytesIO()
            tts.tts_to_file(text=text, file_path=audio_buffer)
            audio_buffer.seek(0)
            
            return audio_buffer.getvalue()
            
        except ImportError:
            logger.warning("Coqui TTS not installed, using fallback")
            return await self._generate_placeholder_audio(text)
    
    async def _generate_placeholder_audio(self, text: str) -> bytes:
        """Generate placeholder audio for development."""
        
        # Create silent audio (will be replaced in production)
        # This is a minimal valid MP3
        placeholder_mp3 = bytes([
            0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])
        
        return placeholder_mp3
    
    async def _get_placeholder_audio_url(self) -> str:
        """Get placeholder audio URL."""
        audio_data = await self._generate_placeholder_audio("")
        
        filename = f"audio/placeholder_{uuid.uuid4()}.mp3"
        
        url = await self.storage.upload_file(
            file_data=audio_data,
            filename=filename,
            content_type="audio/mpeg",
        )
        
        return url
    
    def get_available_voices(self) -> dict:
        """Get list of available voices."""
        return {
            "voices": [
                {
                    "id": voice_id,
                    "name": name,
                    "language": "en",
                    "gender": "male" if "male" in voice_id else "female",
                }
                for voice_id, name in self.voices.items()
            ]
        }
    
    async def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """Estimate audio duration from text."""
        
        # Average speaking rate: ~150 words per minute
        words = len(text.split())
        minutes = words / 150
        seconds = minutes * 60
        
        # Adjust for speed
        return seconds / speed
