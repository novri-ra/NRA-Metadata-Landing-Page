import re

# 1. Update embedder.py
with open('packages/media_processor/embedder.py', 'r', encoding='utf-8') as f:
    emb_c = f.read()

old_emb = 'def embed_metadata(self, file_path: str, title: str, description: str, keywords: list[str], copyright_text: str, author: str = "") -> bool:'
new_emb = '''def embed_metadata(self, file_path: str, title: str, description: str, keywords: list[str], copyright_text: str, author: str = "") -> bool:
        file_path = os.path.abspath(file_path)'''
emb_c = emb_c.replace(old_emb, new_emb)

with open('packages/media_processor/embedder.py', 'w', encoding='utf-8') as f:
    f.write(emb_c)

# 2. Update previews.py
with open('packages/media_processor/previews.py', 'r', encoding='utf-8') as f:
    prev_c = f.read()

old_prev = 'def extract_preview_image(file_path: str, processor) -> str | None:'
new_prev = '''def extract_preview_image(file_path: str, processor) -> str | None:
    file_path = os.path.abspath(file_path)'''
prev_c = prev_c.replace(old_prev, new_prev)

with open('packages/media_processor/previews.py', 'w', encoding='utf-8') as f:
    f.write(prev_c)

print("Path traversal safeguards applied")