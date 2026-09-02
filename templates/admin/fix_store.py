import re

with open('store.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace hardcoded colors with theme-friendly tailwind classes
text = text.replace('bg-[#0e1628]', 'bg-card')
text = text.replace('bg-[#050810]', 'bg-gray-900')
text = text.replace('bg-[#16223f]', 'bg-gray-800')
text = text.replace('hover:bg-[#1e2f5c]', 'hover:bg-gray-700')
text = text.replace('disabled:bg-[#1e2f5c]', 'disabled:bg-gray-800')
text = text.replace('bg-[#1e2f5c]', 'bg-gray-700')

# Borders
text = text.replace('border-blue-900/30', 'border-gray-800 theme-border')
text = text.replace('border-[#1e2f5c]', 'border-gray-700 theme-border')
text = text.replace('hover:border-blue-900', '') # let theme handle hover borders if needed, or just remove

# Text
text = text.replace('text-blue-500', 'text-blue-500 theme-text')
text = text.replace('peer-checked:border-blue-500', 'peer-checked:border-blue-500 theme-border-peer')

with open('store.html', 'w', encoding='utf-8') as f:
    f.write(text)
