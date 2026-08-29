import re

with open('templates/profile.html', 'r', encoding='utf-8') as f:
    text = f.read()

scripts = re.findall(r'<script>(.*?)</script>', text, flags=re.DOTALL)
for i, script in enumerate(scripts):
    with open(f'temp_script_{i}.js', 'w', encoding='utf-8') as sf:
        sf.write(script)
