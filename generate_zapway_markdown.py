import os
import json

EXTENSION_DIR = '/Users/Marci.Holm/Applications/NorthWay-2.0/northway_extension'
OUTPUT_FILE = '/Users/Marci.Holm/Applications/NorthWay-2.0/zapway_completo.md'

with open(os.path.join(EXTENSION_DIR, 'manifest.json'), 'r') as f:
    manifest = json.load(f)

markdown_content = f"# ZapWay Extension v{manifest.get('version', 'Unknown')}\n\n"
markdown_content += f"## Description\n{manifest.get('description', '')}\n\n"

markdown_content += "## Architecture & Directory Structure\n"
markdown_content += "```text\n"
for root, dirs, files in os.walk(EXTENSION_DIR):
    if 'icons' in dirs: dirs.remove('icons')
    level = root.replace(EXTENSION_DIR, '').count(os.sep)
    indent = ' ' * 4 * (level)
    markdown_content += f"{indent}{os.path.basename(root)}/\n"
    subindent = ' ' * 4 * (level + 1)
    for f in sorted(files):
        if not f.endswith('.zip') and not f.startswith('.'):
            markdown_content += f"{subindent}{f}\n"
markdown_content += "```\n\n"

markdown_content += "---\n\n## 📂 Files Source Code\n\n"

def append_file(filepath, title):
    global markdown_content
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            ext = filepath.split('.')[-1]
            lang = ext if ext in ['js', 'json', 'css', 'html'] else 'text'
            markdown_content += f"### `{title}`\n\n```{lang}\n{content}\n```\n\n"
    except Exception as e:
        markdown_content += f"### `{title}`\n\n*Error reading file: {e}*\n\n"


append_file(os.path.join(EXTENSION_DIR, 'manifest.json'), 'manifest.json')

for dir_name in ['popup', 'scripts']:
    dir_path = os.path.join(EXTENSION_DIR, dir_name)
    if os.path.exists(dir_path):
        for filename in sorted(os.listdir(dir_path)):
            if filename.startswith('.'): continue
            filepath = os.path.join(dir_path, filename)
            if os.path.isfile(filepath):
                append_file(filepath, f"{dir_name}/{filename}")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(markdown_content)

print(f"Content written to {OUTPUT_FILE}")
