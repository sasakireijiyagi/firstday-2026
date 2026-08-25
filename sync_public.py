# confirm-src.html（平文の元データ）→ index.html（公開ページ）へスポット情報を同期する。
# 写真は img/ に書き出してファイル参照にする（公開ページは遅延読み込みできるようにするため）。
# 使い方: python3 sync_public.py
import re, json, base64, os, pathlib, io, urllib.parse
from PIL import Image

ROOT = pathlib.Path(__file__).parent
IMG = ROOT / "img"
IMG.mkdir(exist_ok=True)

src = (ROOT / "confirm-src.html").read_text(encoding="utf-8")
cfg = json.loads(re.search(r'<script id="site-config" type="application/json">(.*?)</script>', src, re.S).group(1))

# 2026-08-24: 紹介文(desc)も公開ページに掲載する方針に変更（各団体の連絡先を含む）
KEYS = ["name", "shortName", "area", "day", "time", "lat", "lng", "meta", "address", "link", "mapQuery", "desc"]
pub, kept = [], set()
for i, sp in enumerate(cfg["spots"]):
    rec = {k: sp[k] for k in KEYS if sp.get(k) not in (None, "")}
    photo = sp.get("photo", "")
    if photo.startswith("data:image/"):
        ext = "jpg" if "jpeg" in photo.split(",", 1)[0] else "png"
        fname = f"spot-{i}.{ext}"
        raw = base64.b64decode(photo.split(",", 1)[1])
        (IMG / fname).write_bytes(raw)
        rec["photo"] = f"img/{fname}"
        # 画像の実寸を持たせると、読み込み前でもブラウザが高さを確保できる
        with Image.open(io.BytesIO(raw)) as _im:
            rec["photoW"], rec["photoH"] = _im.size
        kept.add(fname)
    pub.append(rec)

# 使われなくなった画像を掃除（写真が差し替え・削除されたとき用）
for f in IMG.glob("spot-*"):
    if f.name not in kept:
        f.unlink()
        print("removed stale image:", f.name)

block = ('<script id="spots-data" type="application/json">[\n'
         + ',\n'.join('    ' + json.dumps(p, ensure_ascii=False) for p in pub)
         + '\n  ]</script>')
idx = (ROOT / "index.html").read_text(encoding="utf-8")
idx, n = re.subn(r'<script id="spots-data" type="application/json">\[.*?\]</script>', lambda m: block, idx, flags=re.S)
assert n == 1, "spots-data block not found"

# --- 構造化データ（schema.org Event）を生成 ---
SITE = "https://firstday2026.sasakireijiyagi.com/"
DATES = {"8/27": "2026-08-27", "8/28": "2026-08-28"}

def to_iso(day_str, time_str, which):
    """'9:00–15:00（…）' から開始/終了時刻の ISO 文字列を作る"""
    date = DATES[which]
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*[–\-~]\s*(\d{1,2}):(\d{2})", time_str or "")
    if not m:
        return f"{date}T09:00:00+09:00", f"{date}T15:00:00+09:00"
    a, b, c, d2 = m.groups()
    return f"{date}T{int(a):02d}:{b}:00+09:00", f"{date}T{int(c):02d}:{d2}:00+09:00"

events = []
for sp in pub:
    for key in ("8/27", "8/28"):
        if key not in sp.get("day", ""):
            continue
        start, end = to_iso(sp["day"], sp.get("time", ""), key)
        ev = {
            "@type": "Event",
            "name": f"{sp['name']}（糸島夏休み明けプロジェクト2026）",
            "startDate": start,
            "endDate": end,
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "isAccessibleForFree": True,
            "inLanguage": "ja",
            "url": SITE,
            "organizer": {"@type": "Organization", "name": "糸島子どもの居場所プロジェクト／九州大学佐々木研究室"},
            "location": {
                "@type": "Place",
                "name": sp["name"],
                "address": {"@type": "PostalAddress", "addressCountry": "JP",
                            "addressRegion": "福岡県", "addressLocality": "糸島市",
                            "streetAddress": re.sub(r"^〒[0-9\-]+\s*", "", sp.get("address", ""))},
                "geo": {"@type": "GeoCoordinates", "latitude": sp["lat"], "longitude": sp["lng"]},
            },
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "JPY",
                       "availability": "https://schema.org/InStock", "url": SITE},
        }
        if sp.get("desc"):
            ev["description"] = re.sub(r"<[^>]+>", "", sp["desc"])
        if sp.get("photo"):
            ev["image"] = SITE + sp["photo"]
        events.append(ev)

# --- スポット一覧を静的HTMLとしても書き出す（JavaScript無しでも読めるように） ---
def day_class(day):
    d = day or ""
    a, b = "8/27" in d, "8/28" in d
    return "both" if (a and b) else ("day28" if b else "day27")

def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

cards = []
for i, sp in enumerate(pub):
    wide = " wide" if len(pub) % 2 == 1 and i == len(pub) - 1 else ""
    gmap = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(sp.get("mapQuery") or sp.get("address", ""))
    title = (f'<a href="{sp["link"]}" target="_blank" rel="noopener">{esc(sp["name"])}</a>'
             if sp.get("link") else esc(sp["name"]))
    parts = [f'<article class="place card{wide}" id="spot-{i}">',
             f'<h3>{title}<span class="area">【{esc(sp.get("area",""))}】</span></h3>',
             f'<div class="time"><span class="day-badge {day_class(sp.get("day"))}">{esc(sp.get("day",""))}</span> {esc(sp.get("time",""))}</div>',
             f'<div class="meta">{sp.get("meta","")}</div>']
    if sp.get("desc"):
        parts.append(f'<p class="desc">{sp["desc"]}</p>')   # descにはtelリンクを含むためエスケープしない
    if sp.get("photo"):
        parts.append(f'<div class="photo"><img src="{sp["photo"]}" alt="{esc(sp["name"])}のようす" '
                     f'width="{sp.get("photoW","")}" height="{sp.get("photoH","")}" loading="lazy" decoding="async"></div>')
    if sp.get("mapQuery"):
        parts.append(f'<div class="map"><iframe src="https://maps.google.com/maps?q='
                     f'{urllib.parse.quote(sp["mapQuery"])}&amp;z=15&amp;output=embed" loading="lazy" '
                     f'referrerpolicy="no-referrer-when-downgrade" title="{esc(sp["name"])}の地図"></iframe></div>')
    parts.append(f'<div class="address">{esc(sp.get("address",""))}</div>')
    links = f'<a href="{gmap}" target="_blank" rel="noopener">地図を開く</a>'
    if sp.get("link"):
        links += f'<a href="{sp["link"]}" target="_blank" rel="noopener">サイト</a>'
    parts.append(f'<div class="links">{links}</div>')
    parts.append('</article>')
    cards.append("\n      ".join(parts))

list_html = '<div id="spots-list" class="grid cols-2">\n      ' + "\n      ".join(cards) + '\n    </div>'
idx, n3 = re.subn(r'<div id="spots-list" class="grid cols-2">.*?</div>\s*(?=\n\s*</section>)',
                  lambda m: list_html, idx, flags=re.S)
assert n3 == 1, "spots-list block not found"

jsonld = json.dumps({"@context": "https://schema.org", "@graph": events}, ensure_ascii=False, indent=2)
idx, n2 = re.subn(r'(<script id="jsonld" type="application/ld\+json">).*?(</script>)',
                  lambda m: m.group(1) + jsonld + m.group(2), idx, flags=re.S)
assert n2 == 1, "jsonld block not found"
(ROOT / "index.html").write_text(idx, encoding="utf-8")

print(f"synced {len(pub)} spots / photos: {sorted(kept)}")
print("desc:", [p['name'] for p in pub if p.get('desc')])
