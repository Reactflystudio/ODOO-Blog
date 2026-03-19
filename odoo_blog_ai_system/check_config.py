
from config import get_settings

settings = get_settings()
print(f"PROVIDER: {settings.default_llm_provider}")
print(f"MODEL: {settings.gemini_model}")
print(f"API KEY: {settings.google_ai_api_key[:10]}...")
