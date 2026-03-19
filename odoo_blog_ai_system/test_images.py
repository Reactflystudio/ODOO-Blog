import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.image_generator import ImageGenerator
from models.article import Article, ArticleMetadata
from config import get_settings, ImageProvider

async def test_images():
    settings = get_settings()
    print(f"Provider: {settings.image_provider}")
    print(f"API Key for Gemini/Imagen: {settings.google_ai_api_key[:10]}...")
    
    gen = ImageGenerator(provider=ImageProvider.GOOGLE_IMAGEN)
    
    article = Article(title="Teste de Imagem")
    article.metadata = ArticleMetadata(keyword_primary="marketing digital")
    
    print("Gerando imagens...")
    article = await gen.generate_article_images(
        article=article,
        content_image_count=1
    )
    
    if article.cover_image:
        print(f"Capa gerada: {article.cover_image.local_path}")
    else:
        print("Falha ao gerar capa.")
        
    if article.content_images:
        print(f"Imagens de conteudo: {len(article.content_images)}")
    else:
        print("Falha ao gerar imagens de conteudo.")

if __name__ == "__main__":
    asyncio.run(test_images())
