"""Teste direto do provider Gemini."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings
from providers.gemini_provider import GeminiProvider


async def test_gemini():
    settings = get_settings()
    
    print(f"Default provider: {settings.default_llm_provider.value}")
    print(f"Gemini API key: {settings.google_ai_api_key[:15]}..." if settings.google_ai_api_key else "Gemini API key: EMPTY!")
    print(f"Gemini model: {settings.gemini_model}")
    print(f"Fallback order: {[p.value for p in settings.llm_provider_fallback_order]}")
    print()
    
    if not settings.google_ai_api_key:
        print("ERROR: Gemini API key not configured!")
        return
    
    provider = GeminiProvider(
        api_key=settings.google_ai_api_key,
        model=settings.gemini_model,
        temperature=0.7,
        max_tokens=1024,
    )
    
    print("Testing health check...")
    healthy = await provider.health_check()
    print(f"Health check: {'OK' if healthy else 'FAILED'}")
    print()
    
    print("Testing simple generation...")
    try:
        response = await provider.generate(
            prompt="Responda apenas: 'Ola mundo! Gemini funcionando!'",
            system_prompt="Voce e um assistente de teste.",
        )
        print(f"Success: {response.success}")
        print(f"Content: {response.content[:200]}")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.total_tokens}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_gemini())
