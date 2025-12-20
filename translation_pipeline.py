# translation_pipeline.py - Azure Translator Ready (V2 Bidirectional)
import os
import base64
import io
from typing import Optional, Dict
import json

# Azure Translator (will be enabled when you add credentials)
try:
    import requests
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("⚠️  requests not available - Azure Translator disabled")

# Text-to-Speech (optional for now)
try:
    from gtts import gTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("⚠️  gTTS not available - Text-to-speech disabled")


class TranslationPipeline:
    """
    Handles bidirectional translation using Azure Translator
    V2: Any-to-any language translation
    """
    
    def __init__(self):
        """Initialize Azure Translator"""
        
        # Azure Translator Configuration
        self.azure_key = os.getenv("AZURE_TRANSLATOR_KEY")
        self.azure_endpoint = os.getenv(
            "AZURE_TRANSLATOR_ENDPOINT",
            "https://api.cognitive.microsofttranslator.com"
        )
        self.azure_region = os.getenv("AZURE_TRANSLATOR_REGION", "global")
        
        # Check if Azure is configured
        self.azure_enabled = bool(self.azure_key and AZURE_AVAILABLE)
        
        if not self.azure_enabled:
            print("⚠️  Azure Translator NOT configured - running in DEMO mode")
            print("   Set AZURE_TRANSLATOR_KEY to enable translation")
        else:
            print("✅ Azure Translator initialized")
            print(f"   Region: {self.azure_region}")
        
        # Supported language codes (Azure supports 100+)
        self.supported_languages = {
            "en": "English",
            "zh-Hans": "Chinese (Simplified)",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "ja": "Japanese",
            "ko": "Korean",
            "pt": "Portuguese",
            "it": "Italian",
            "ru": "Russian",
            "ar": "Arabic",
            "hi": "Hindi",
            "tr": "Turkish",
            "nl": "Dutch",
            "pl": "Polish",
            "vi": "Vietnamese",
            "th": "Thai",
            "fa": "Persian (Farsi)",
            "da": "Danish",
            "sv": "Swedish",
            "no": "Norwegian",
            "fi": "Finnish",
        }
        
        # Language code mapping (frontend code -> Azure code)
        self.language_map = {
            "zh": "zh-Hans",  # Map simplified Chinese
            "en": "en",
            "es": "es",
            "fr": "fr",
            "de": "de",
            "ja": "ja",
            "ko": "ko",
            "pt": "pt",
            "it": "it",
            "ru": "ru",
            "ar": "ar",
            "hi": "hi",
            "tr": "tr",
            "nl": "nl",
            "pl": "pl",
            "vi": "vi",
            "th": "th",
            "fa": "fa",
            "da": "da",
            "sv": "sv",
            "no": "no",
            "fi": "fi",
        }
        
        print(f"✅ Translation pipeline initialized")
        print(f"   Supported languages: {len(self.supported_languages)}")
        print(f"   Mode: {'Azure Translation' if self.azure_enabled else 'DEMO (no translation)'}")
    
    async def process_text(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> Dict:
        """
        Translate text from source language to target language
        
        Args:
            text: Text to translate
            source_lang: Source language code (e.g., "en", "zh")
            target_lang: Target language code (e.g., "es", "fr")
        
        Returns:
            dict with status, original_text, translated_text, translated_audio
        """
        
        try:
            # Map language codes to Azure format
            azure_source = self.language_map.get(source_lang, source_lang)
            azure_target = self.language_map.get(target_lang, target_lang)
            
            # If same language, no translation needed
            if source_lang == target_lang:
                translated_text = text
                print(f"ℹ️  Same language ({source_lang}), no translation needed")
            
            # If Azure is enabled, translate
            elif self.azure_enabled:
                translated_text = await self._translate_with_azure(
                    text, 
                    azure_source, 
                    azure_target
                )
                print(f"✅ Translated: {source_lang} → {target_lang}")
                print(f"   Original: {text}")
                print(f"   Translated: {translated_text}")
            
            # Demo mode - just return original text with a note
            else:
                translated_text = f"[DEMO MODE - No translation] {text}"
                print(f"⚠️  Demo mode: returning original text")
            
            # Generate TTS audio (optional)
            audio_base64 = ""
            if TTS_AVAILABLE:
                audio_base64 = await self._text_to_speech(translated_text, target_lang)
            
            return {
                "status": "success",
                "original_text": text,
                "translated_text": translated_text,
                "translated_audio": audio_base64,
                "source_lang": source_lang,
                "target_lang": target_lang
            }
        
        except Exception as e:
            print(f"❌ Error in translation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "original_text": text,
                "translated_text": text,  # Return original on error
                "translated_audio": "",
                "source_lang": source_lang,
                "target_lang": target_lang
            }
    
    async def _translate_with_azure(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> str:
        """
        Translate text using Azure Translator API
        
        Args:
            text: Text to translate
            source_lang: Azure source language code
            target_lang: Azure target language code
        
        Returns:
            Translated text
        """
        
        if not self.azure_enabled:
            return text
        
        try:
            # Azure Translator API endpoint
            path = '/translate'
            constructed_url = self.azure_endpoint + path
            
            # Request parameters
            params = {
                'api-version': '3.0',
                'from': source_lang,
                'to': target_lang
            }
            
            # Request headers
            headers = {
                'Ocp-Apim-Subscription-Key': self.azure_key,
                'Ocp-Apim-Subscription-Region': self.azure_region,
                'Content-type': 'application/json',
            }
            
            # Request body
            body = [{
                'text': text
            }]
            
            # Make request
            response = requests.post(
                constructed_url, 
                params=params, 
                headers=headers, 
                json=body,
                timeout=10
            )
            
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            translated_text = result[0]['translations'][0]['text']
            
            return translated_text
        
        except requests.exceptions.Timeout:
            print(f"❌ Azure Translator timeout")
            return text
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Azure Translator error: {e}")
            return text
        
        except (KeyError, IndexError) as e:
            print(f"❌ Error parsing Azure response: {e}")
            return text
    
    async def _text_to_speech(self, text: str, language: str) -> str:
        """
        Convert text to speech using gTTS (optional)
        
        Args:
            text: Text to convert
            language: Language code
        
        Returns:
            Base64 encoded audio (or empty string if TTS unavailable)
        """
        
        if not TTS_AVAILABLE:
            return ""
        
        try:
            # Map to gTTS language code
            tts_lang_map = {
                "zh": "zh-CN",
                "zh-Hans": "zh-CN",
                "en": "en",
                "es": "es",
                "fr": "fr",
                "de": "de",
                "ja": "ja",
                "ko": "ko",
                "pt": "pt",
                "it": "it",
                "ru": "ru",
                "ar": "ar",
                "hi": "hi",
                "tr": "tr",
                "nl": "nl",
                "pl": "pl",
                "vi": "vi",
                "th": "th",
                "fa": "fa",
            }
            
            tts_lang = tts_lang_map.get(language, "en")
            
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
            print(f"❌ TTS error: {e}")
            return ""
    
    def get_supported_languages(self) -> Dict:
        """Get list of supported languages"""
        return {
            "mode": "bidirectional",
            "azure_enabled": self.azure_enabled,
            "tts_enabled": TTS_AVAILABLE,
            "total_languages": len(self.supported_languages),
            "languages": list(self.language_map.keys()),
            "language_names": self.supported_languages
        }
    
    def validate_language(self, language: str) -> bool:
        """
        Check if a language code is supported
        
        Args:
            language: Language code to validate
            
        Returns:
            True if supported, False otherwise
        """
        return language in self.language_map
    
    def get_language_info(self, language: str) -> Optional[Dict]:
        """
        Get information about a specific language
        
        Args:
            language: Language code
            
        Returns:
            Dict with language info or None if not supported
        """
        if not self.validate_language(language):
            return None
        
        azure_code = self.language_map.get(language, language)
        
        return {
            "code": language,
            "azure_code": azure_code,
            "name": self.supported_languages.get(azure_code, "Unknown"),
            "supported": True
        }
    
    async def process_audio_chunk(
        self, 
        audio_data: str, 
        source_lang: str, 
        target_lang: str
    ) -> Dict:
        """
        Process audio chunk (placeholder for future voice support)
        
        Args:
            audio_data: Base64 encoded audio
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            dict with status and message
        """
        
        return {
            "status": "error",
            "error": "Audio processing not yet implemented. Use text chat for now.",
            "source_lang": source_lang,
            "target_lang": target_lang
        }