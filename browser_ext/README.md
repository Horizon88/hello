# 🌏 Land Scout — DOL + Facebook auto-capture

A Chrome/Edge extension that silently captures Thai land parcels and Facebook land-sale posts as you browse. One-click push everything into your Land app's Deed Log.

## Why

Copy-paste one-at-a-time doesn't scale. You already log into DOL Landsmaps and Facebook every day. This extension watches those tabs and grabs the data automatically.

## Install (unpacked — 30 seconds)

1. Open Chrome / Edge → `chrome://extensions/`
2. Toggle **Developer mode** (top-right)
3. Click **Load unpacked** → pick this `browser_ext/` folder
4. Pin the extension icon to your toolbar (jigsaw-piece → thumbtack)

## Use

**On DOL Landsmaps** (`landsmaps.dol.go.th`):
- Log in with your Thai ID as usual
- Click any parcel — the info panel appears
- Extension silently captures: deed #, coord, area, sub-district, valuation
- Green toast bottom-right confirms capture

**On Facebook** (`facebook.com` — feed, groups, marketplace):
- Scroll normally
- Extension detects any post with "ราคา" + "ไร่" (price + rai) signals
- Blue toast confirms new captures

**When you're ready to review:**
- Click the extension icon
- See totals: DOL parcels, FB posts
- Click **📤 Send all → Land app** — opens the app with everything imported into your Deed Log
- Or **📋 Copy as TSV** to paste elsewhere

## Privacy

- Runs entirely in your browser
- No data leaves your device except when you click "Send all"
- Auth cookies (Thai ID, FB session) never touched
- Storage: `chrome.storage.local` (browser-only)

## What it captures

**DOL parcels:**
- Title deed # / โฉนดเลขที่
- Coord (lat, lng)
- Area (rai + ngan + wah, plus decimal rai)
- Sub-district, district, province
- Map sheet number
- Treasury valuation (฿/sqwa)

**FB posts** (heuristic — post must contain both rai + price):
- Coord (from Google Maps link or plain lat/lng in text)
- Rai count
- Price THB (auto-multiplies per-rai to total)
- Contact phone (Thai formats)
- Title hint (Chanote / SPK)
- Location keywords
- Text preview for dedup

## Updating

The extension is stateless — pull the latest `browser_ext/` from the repo, then in `chrome://extensions/` click the refresh icon on the Land Scout card.
