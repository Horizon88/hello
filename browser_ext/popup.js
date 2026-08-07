const APP_URL = 'https://raw.githack.com/Horizon88/hello/master/docs/index.html';

async function refresh(){
  const {parcels = {}, fb_posts = {}} = await chrome.storage.local.get(['parcels', 'fb_posts']);
  document.getElementById('dolCount').textContent = Object.keys(parcels).length;
  document.getElementById('fbCount').textContent = Object.keys(fb_posts).length;
}

document.getElementById('pushBtn').onclick = async () => {
  const {parcels = {}, fb_posts = {}} = await chrome.storage.local.get(['parcels', 'fb_posts']);
  const all = { dol: Object.values(parcels), fb: Object.values(fb_posts) };
  if(all.dol.length === 0 && all.fb.length === 0){
    alert('No captured items yet. Browse DOL or FB first — the extension captures silently as you scroll.');
    return;
  }
  // Encode compact JSON in URL hash
  const payload = btoa(unescape(encodeURIComponent(JSON.stringify(all))));
  chrome.tabs.create({url: APP_URL + '#captured=' + payload});
};

document.getElementById('copyBtn').onclick = async () => {
  const {parcels = {}, fb_posts = {}} = await chrome.storage.local.get(['parcels', 'fb_posts']);
  const rows = [];
  rows.push(['source','deed_or_id','lat','lng','rai','price_thb','location','contact','url'].join('\t'));
  for(const p of Object.values(parcels)){
    rows.push(['dol', p.deed||'', p.lat||'', p.lng||'', p.rai_decimal||'', '', p.subdistrict||'', '', p.source_url||''].join('\t'));
  }
  for(const p of Object.values(fb_posts)){
    rows.push(['fb', p.id, p.lat||'', p.lng||'', p.rai||'', p.price_thb||'', p.location||'', p.contact||'', p.source_url||''].join('\t'));
  }
  await navigator.clipboard.writeText(rows.join('\n'));
  const btn = document.getElementById('copyBtn');
  const orig = btn.textContent;
  btn.textContent = '✓ Copied ' + (rows.length - 1) + ' rows';
  setTimeout(()=>{ btn.textContent = orig; }, 2000);
};

document.getElementById('clearBtn').onclick = async () => {
  if(!confirm('Clear all captured DOL parcels and FB posts?')) return;
  await chrome.storage.local.set({parcels: {}, fb_posts: {}});
  refresh();
};

refresh();
