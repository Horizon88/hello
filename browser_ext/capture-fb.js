// Auto-capture Facebook posts that look like Thai land-sale listings.
// Watches your feed / groups / marketplace and pulls posts containing
// price + rai signals.

(() => {
  const store = {
    async load(){ return (await chrome.storage.local.get('fb_posts')).fb_posts || {}; },
    async save(p){ await chrome.storage.local.set({fb_posts: p}); },
  };

  function looksLikeLandPost(text){
    if(!text || text.length < 40 || text.length > 4000) return false;
    // Must mention rai OR sqwa
    const hasArea = /ไร่|\brai\b|ตารางวา|sqwa|sq\.?\s*wah/i.test(text);
    // Must mention price
    const hasPrice = /ราคา|price|บาท|baht|฿|thb\b|ล้าน|million/i.test(text);
    // Bonus signals: coord, chanote, phone
    return hasArea && hasPrice;
  }

  function extractFbPost(text, article){
    const out = { source: 'fb', captured_at: new Date().toISOString() };
    const m = (re) => (text.match(re) || [])[1];
    // Coord
    let c = text.match(/[?&]q=(-?\d+\.\d+)[, ]+(-?\d+\.\d+)/)
         || text.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/)
         || text.match(/(-?\d{1,2}\.\d{4,})[,\s]+(\d{1,3}\.\d{4,})/);
    if(c && parseFloat(c[1])>5 && parseFloat(c[1])<21){
      out.lat = parseFloat(c[1]); out.lng = parseFloat(c[2]);
    }
    // Rai
    const r = m(/(\d[\d.,]*)\s*ไร่|(\d[\d.,]*)\s*\brai\b/i);
    if(r) out.rai = parseFloat(r.replace(/,/g,''));
    // Price
    const p = m(/ราคา\s*[:.]?\s*([\d,]+)/) || m(/price\s*[:.]?\s*([\d,]+)/i) || m(/฿\s*([\d,]{5,})/);
    if(p) out.price_thb = parseInt(p.replace(/,/g,''));
    // Per-rai vs total
    if(out.price_thb && out.rai && /ต่อไร่|per\s*rai|\/rai|\/ไร่/i.test(text)){
      out.price_thb = out.price_thb * out.rai;
      out.price_note = 'converted from per-rai';
    }
    // Contact
    const ph = text.match(/\b0\d[- ]?\d{3,4}[- ]?\d{4}\b/);
    if(ph) out.contact = ph[0].replace(/[- ]/g,'');
    // Title hint
    if(/โฉนด|chanote|krut\s*daeng/i.test(text)) out.title_hint = 'Chanote';
    else if(/สปก|spk/i.test(text)) out.title_hint = 'SPK (warning)';
    // Location keywords (Thai)
    const loc = m(/(?:ตั้งอยู่|location|ที่ตั้ง)[^:]*[:.]?\s*([A-Za-z\s฀-๿,]{5,60})/);
    if(loc) out.location = loc.trim();
    // Fingerprint (hash of first 200 chars) to dedup
    out.text_preview = text.slice(0, 300).replace(/\s+/g, ' ').trim();
    return out;
  }

  async function scanArticles(){
    const articles = document.querySelectorAll('[role="article"]');
    const posts = await store.load();
    let newCount = 0;
    for(const a of articles){
      const text = a.innerText;
      if(!looksLikeLandPost(text)) continue;
      // Hash the first 300 chars as ID
      let h = 0; const s = text.slice(0, 300);
      for(let i=0; i<s.length; i++) h = ((h<<5) - h + s.charCodeAt(i)) | 0;
      const id = 'fb_' + Math.abs(h).toString(36);
      if(posts[id]) continue;
      posts[id] = { id, ...extractFbPost(text, a), source_url: location.href };
      newCount++;
    }
    if(newCount){
      await store.save(posts);
      showToast(`📘 Captured ${newCount} new land posts · ${Object.keys(posts).length} total`);
    }
  }

  function showToast(msg){
    let t = document.getElementById('__land_scout_fb_toast');
    if(!t){
      t = document.createElement('div');
      t.id = '__land_scout_fb_toast';
      t.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#1a2a3a;color:#4fa3ff;border:1px solid #4fa3ff;padding:10px 14px;border-radius:6px;z-index:99999;font-family:sans-serif;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,0.4)';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(t._h);
    t._h = setTimeout(()=>{ t.style.opacity = '0'; t.style.transition='opacity 0.4s'; }, 3500);
  }

  const debounced = (() => {
    let h; return () => { clearTimeout(h); h = setTimeout(scanArticles, 800); };
  })();
  new MutationObserver(debounced).observe(document.body, {childList:true, subtree:true});
  setTimeout(scanArticles, 2000);
})();
