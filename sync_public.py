# confirm-src.html（平文の元データ）→ index.html（公開ページ）へスポット情報を同期する。
# 写真は img/ に書き出してファイル参照にする（公開ページは遅延読み込みできるようにするため）。
# 使い方: python3 sync_public.py
import re, json, base64, os, pathlib

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
        (IMG / fname).write_bytes(base64.b64decode(photo.split(",", 1)[1]))
        rec["photo"] = f"img/{fname}"
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
(ROOT / "index.html").write_text(idx, encoding="utf-8")

print(f"synced {len(pub)} spots / photos: {sorted(kept)}")
print("desc:", [p['name'] for p in pub if p.get('desc')])
