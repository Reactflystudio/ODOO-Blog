import json
p = r"c:\Users\ReactFlow\Documents\ALEXANDRE\NEUBER\EMPURRAO DIGITAL\ODOO\odoo_blog_ai_system\data\generated_articles\6105d965-a735-479e-a61c-da3276729e3a\article.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
d["blog_id"] = 4
# Fix title if it's the generic one
if d["title"] == "Guia sobre marketing digital":
    d["title"] = "Marketing Digital Político: Estratégias Vencedoras para Eleições 2026"
# Fix content_html if it has the JSON block
if "```json" in d["content_html"]:
    import re
    m = re.search(r'"content_html":\s*"(.*?)"', d["content_html"], re.DOTALL)
    if m:
        c = m.group(1).replace('\\"', '"').replace('\\n', '\n')
        d["content_html"] = c
with open(p, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print("FIXED")
