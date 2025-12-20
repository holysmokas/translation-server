# app/services/translation_pipeline.py - V2 Bidirectional
import os
import base64
import io
#from groq import Groq
#from google.cloud import translate_v2 as translate
from gtts import gTTS
import tempfile
from pathlib import Path
from typing import Optional

class TranslationPipeline:
    """
    Handles the complete translation pipeline: Speech → Text → Translation → Speech
    V2: Now supports any-to-any language translation
    """
    
    def __init__(self):
        """Initialize translation services"""
        
        # Groq client for Whisper (speech-to-text)
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.groq_client = Groq(api_key=groq_api_key)
        
        # Google Translate client
        try:
            self.translate_client = translate.Client()
        except Exception as e:
            raise ValueError(f"Google Translate setup failed: {e}")
        
        # Expanded language code mapping for gTTS (V2)
        self.tts_language_map = {
            # Original 6 languages
            "en": "en",     # English
            "zh": "zh-CN",  # Chinese (Simplified)
            "es": "es",     # Spanish
            "fr": "fr",     # French
            "fa": "fa",     # Persian (Farsi) - Limited support
            "ru": "ru",     # Russian
            
            # New languages (V2)
            "de": "de",     # German
            "ja": "ja",     # Japanese
            "ko": "ko",     # Korean
            "pt": "pt",     # Portuguese
            "it": "it",     # Italian
            "ar": "ar",     # Arabic
            "hi": "hi",     # Hindi
            "tr": "tr",     # Turkish
            "nl": "nl",     # Dutch
            "pl": "pl",     # Polish
            "vi": "vi",     # Vietnamese
            "th": "th",     # Thai
        }
        
        # Whisper language codes (same as above for most)
        self.whisper_language_map = {
            "en": "en",
            "zh": "zh",
            "es": "es",
            "fr": "fr",
            "fa": "fa",
            "ru": "ru",
            "de": "de",
            "ja": "ja",
            "ko": "ko",
            "pt": "pt",
            "it": "it",
            "ar": "ar",
            "hi": "hi",
            "tr": "tr",
            "nl": "nl",
            "pl": "pl",
            "vi": "vi",
            "th": "th",
        }
        
        print("✅ Translation pipeline V2 initialized")
        print(f"   Supported languages: {len(self.tts_language_map)}")
        print(f"   Any-to-any translation enabled")
    
    async def process_audio_chunk(
        self, 
        audio_data: str, 
        source_lang: str, 
        target_lang: str
    ) -> dict:
        """
        Process audio chunk through full pipeline
        
        Args:
            audio_data: Base64 encoded audio
            source_lang: Source language code (e.g., "en", "zh")
            target_lang: Target language code (e.g., "es", "fr")
        
        Returns:
            dict with original_text, translated_text, translated_audio (base64)
        """
        
        try:
            # Step 1: Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Step 2: Speech to Text (Whisper via Groq)
            original_text = await self._transcribe_audio(audio_bytes, source_lang)
            
            if not original_text or len(original_text.strip()) == 0:
                return {
                    "status": "error",
                    "error": "No speech detected"
                }
            
            # Step 3: Translate text (if languages are different)
            if source_lang == target_lang:
                # Same language - no translation needed
                translated_text = original_text
            else:
                translated_text = self._translate_text(original_text, target_lang, source_lang)
            
            # Step 4: Text to Speech
            translated_audio_base64 = await self._text_to_speech(translated_text, target_lang)
            
            return {
                "status": "success",
                "original_text": original_text,
                "translated_text": translated_text,
                "translated_audio": translated_audio_base64,
                "source_lang": source_lang,
                "target_lang": target_lang
            }
        
        except Exception as e:
            print(f"❌ Error in translation pipeline: {e}")
            return {
                "status": "error",
                "error": str(e),
                "source_lang": source_lang,
                "target_lang": target_lang
            }
    
    async def process_text(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> dict:
        """
        Process text-only translation (for testing/debugging)
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            dict with translated_text and translated_audio
        """
        
        try:
            # Step 1: Translate text (if languages are different)
            if source_lang == target_lang:
                # Same language - no translation needed
                translated_text = text
                print(f"ℹ️  Same language ({source_lang}), no translation needed")
            else:
                translated_text = self._translate_text(text, target_lang, source_lang)
                print(f"✅ Translated: {source_lang} → {target_lang}")
                print(f"   Original: {text}")
                print(f"   Translated: {translated_text}")
            
            # Step 2: Text to Speech
            translated_audio_base64 = await self._text_to_speech(translated_text, target_lang)
            
            return {
                "status": "success",
                "original_text": text,
                "translated_text": translated_text,
                "translated_audio": translated_audio_base64,
                "source_lang": source_lang,
                "target_lang": target_lang
            }
        
        except Exception as e:
            print(f"❌ Error in text translation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "source_lang": source_lang,
                "target_lang": target_lang
            }
    
    async def _transcribe_audio(self, audio_bytes: bytes, language: str) -> str:
        """
        Transcribe audio to text using Groq Whisper
        
        Args:
            audio_bytes: Raw audio bytes
            language: Language code
        
        Returns:
            Transcribed text
        """
        
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name
        
        try:
            # Map language code to Whisper format
            whisper_lang = self.whisper_language_map.get(language, language)
            
            with open(temp_audio_path, "rb") as audio_file:
                # Transcribe using Groq Whisper
                transcription = self.groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    language=whisper_lang if whisper_lang != "auto" else None,
                    response_format="text",
                    temperature=0.0
                )
            
            # Clean up temp file
            Path(temp_audio_path).unlink()
            
            return transcription.strip()
        
        except Exception as e:
            # Clean up temp file
            Path(temp_audio_path).unlink(missing_ok=True)
            print(f"❌ Transcription error: {e}")
            raise e
    
    def _translate_text(
        self, 
        text: str, 
        target_lang: str, 
        source_lang: str = "auto"
    ) -> str:
        """
        Translate text using Google Translate (supports 133+ languages)
        
        Args:
            text: Text to translate
            target_lang: Target language code
            source_lang: Source language code (or "auto" to detect)
        
        Returns:
            Translated text
        """
        
        try:
            if source_lang == "auto":
                source_lang = None
            
            # Google Translate API call
            result = self.translate_client.translate(
                text,
                target_language=target_lang,
                source_language=source_lang
            )
            
            return result['translatedText']
        
        except Exception as e:
            print(f"❌ Translation error ({source_lang} → {target_lang}): {e}")
            # Return original text if translation fails
            return text
    
    async def _text_to_speech(self, text: str, language: str) -> str:
        """
        Convert text to speech and return as base64
        
        Args:
            text: Text to convert
            language: Language code
        
        Returns:
            Base64 encoded audio
        """
        
        try:
            # Map language code to gTTS format
            tts_lang = self.tts_language_map.get(language, "en")
            
            # Check if language is supported by gTTS
            if language not in self.tts_language_map:
                print(f"⚠️  Language {language} not supported by gTTS, using English")
                tts_lang = "en"
            
            # Generate speech
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            
            # Save to bytes buffer
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_buffer.read()).decode('utf-8')
            
            return audio_base64
        
        except Exception as e:
            print(f"❌ TTS error for language {language}: {e}")
            # Return empty audio on error
            return ""
    
    def get_supported_languages(self) -> dict:
        """Get list of supported languages"""
        return {
            "mode": "bidirectional",
            "total_languages": len(self.tts_language_map),
            "languages": list(self.tts_language_map.keys()),
            "tts_support": self.tts_language_map,
            "whisper_support": self.whisper_language_map
        }
    
    def validate_language(self, language: str) -> bool:
        """
        Check if a language code is supported
        
        Args:
            language: Language code to validate
            
        Returns:
            True if supported, False otherwise
        """
        return language in self.tts_language_map
    
    def get_language_info(self, language: str) -> Optional[dict]:
        """
        Get information about a specific language
        
        Args:
            language: Language code
            
        Returns:
            Dict with language info or None if not supported
        """
        if not self.validate_language(language):
            return None
        
        return {
            "code": language,
            "tts_code": self.tts_language_map.get(language),
            "whisper_code": self.whisper_language_map.get(language),
            "supported": True
        }