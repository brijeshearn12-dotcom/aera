import os
import re

patterns = [
    r'(?i)api[_-]?key\s*[:=]\s*[\'"][a-zA-Z0-9_\-]{8,}[\'"]',
    r'(?i)secret\s*[:=]\s*[\'"][a-zA-Z0-9_\-]{8,}[\'"]',
    r'(?i)password\s*[:=]\s*[\'"][a-zA-Z0-9_\-]{8,}[\'"]',
    r'ghp_[a-zA-Z0-9]{36}',
    r'AIza[0-9A-Za-z-_]{35}',
]

exclude_dirs = {'.git', '.venv', '__pycache__', '.pytest_cache'}
suspicious = []

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if file.endswith(('.png', '.parquet', '.joblib', '.pyc')):
            continue
        filepath = os.path.join(root, file)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for pat in patterns:
                    matches = re.findall(pat, content)
                    if matches:
                        suspicious.append((filepath, matches))
        except Exception:
            pass

print("Suspicious secret matches:", len(suspicious))
for path, match in suspicious:
    print(f"  {path}: {match}")

dot_envs = [os.path.join(root, f) for root, dirs, files in os.walk('.') for f in files if f.startswith('.env') and f != '.env.example']
print("Discovered .env files:", dot_envs)
