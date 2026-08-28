with open('templates/store.html', 'r', encoding='utf-8') as f: content = f.read()
import re
content = re.sub(
    r'</div>\s*<button onclick="let v = document\.getElementById',
    '''</div>

<!-- Products List -->
<div class="space-y-6 mb-16" id="products-container">
    {% for p in products %}
    <div class="product-card bg-[#0b0c10] rounded-2xl border-2 border-blue-600 shadow-[0_0_15px_rgba(37,99,235,0.5)] overflow-hidden relative" data-category="{{ p.category }}">
        
        <!-- Top Tags -->
        <div class="absolute top-3 left-3 z-10 flex gap-2">
            <span class="text-[10px] font-bold px-2 py-1 bg-teal-900/80 text-teal-300 border border-teal-500/50 rounded uppercase tracking-widest backdrop-blur-sm shadow-lg">{{ p.category }}</span>
        </div>
        
        <div class="absolute top-3 right-3 z-10 flex gap-1">
            {% set s = p.status | default('SAFE') %}
            {% if s == 'SAFE' %}
                <span class="bg-green-500/90 text-white text-[10px] font-black px-3 py-1 rounded-md uppercase tracking-wider shadow-[0_0_10px_rgba(34,197,94,0.6)]">✅ SAFE</span>
            {% elif s == 'UPDATING' %}
                <span class="bg-yellow-500/90 text-black text-[10px] font-black px-3 py-1 rounded-md uppercase tracking-wider shadow-[0_0_10px_rgba(234,179,8,0.6)] animate-pulse">⚠️ UPDATING</span>
            {% else %}
                <span class="bg-red-600/90 text-white text-[10px] font-black px-3 py-1 rounded-md uppercase tracking-wider shadow-[0_0_10px_rgba(220,38,38,0.6)] animate-pulse">❌ PATCHED</span>
            {% endif %}
        </div>
        
        <!-- Media Section -->
        <div class="relative w-full h-56 bg-black flex items-center justify-center border-b border-gray-800 overflow-hidden group">
            {% if p.media_url %}
                {% if p.media_url.endswith('.mp4') %}
                    <video id="vid-{{ loop.index }}" src="{{ p.media_url }}" class="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition duration-500" loop muted playsinline></video>
                    <!-- Custom Play Button Overlay -->
                    <button onclick="let v = document.getElementById''',
    content
)
with open('templates/store.html', 'w', encoding='utf-8') as f: f.write(content)
