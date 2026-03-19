"""Verifica blogs e tags disponíveis no Odoo e salva em arquivo."""
import xmlrpc.client
import sys
import os
from pathlib import Path

# Adiciona o root do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings

def test_odoo():
    settings = get_settings()
    url = settings.odoo_url
    db = settings.odoo_db
    username = settings.odoo_username
    password = settings.odoo_password
    output_path = Path(__file__).parent / "odoo_diag.txt"

    with open(output_path, "w") as f:
        f.write(f"Conectando a {url}...\n")
        f.write(f"DB: {db}, User: {username}\n")
        
        try:
            common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
            uid = common.authenticate(db, username, password, {})
            if not uid:
                f.write("ERRO: Falha na autenticacao!\n")
                return
            
            f.write(f"Autenticado com sucesso! UID: {uid}\n")
            models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
            
            # 1. List Blogs
            f.write("\n=== Blogs Disponiveis ===\n")
            blogs = models.execute_kw(db, uid, password, 'blog.blog', 'search_read', [[]], {'fields': ['id', 'name']})
            for b in blogs:
                f.write(f"ID: {b['id']} - Nome: {b['name']}\n")
                
            # 2. Check current blog_id from .env
            env_blog_id = settings.odoo_blog_id
            f.write(f"\nBlog ID no .env: {env_blog_id}\n")
            
            exists = any(b['id'] == env_blog_id for b in blogs)
            if not exists:
                f.write(f"AVISO: O blog_id {env_blog_id} NAO FOI ENCONTRADO!\n")
                if blogs:
                    f.write(f"Sugerindo usar o ID {blogs[0]['id']} ({blogs[0]['name']})\n")
            else:
                f.write("O blog_id e valido.\n")

        except Exception as e:
            f.write(f"ERRO: {e}\n")

if __name__ == "__main__":
    test_odoo()
