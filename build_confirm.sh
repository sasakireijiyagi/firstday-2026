#!/bin/bash
# 確認用ページ（パスワード保護）をビルドする
# 使い方: ./build_confirm.sh
set -e
cd "$(dirname "$0")"
npx -y staticrypt confirm-src.html -d confirm -p "itoshima2026ito" \
  --template-title "糸島夏休み明けプロジェクト2026（確認用）" \
  --template-instructions "会場のみなさま向けの確認用ページです。お伝えしているパスワードを入力してください。" \
  --template-button "ひらく" \
  --template-placeholder "パスワード" \
  --remember 30
mv confirm/confirm-src.html confirm/index.html
# 検索避け（確認用ページは検索結果に出さない）
python3 - <<'EOF'
import re, pathlib
p = pathlib.Path("confirm/index.html")
s = p.read_text(encoding="utf-8")
if 'name="robots"' not in s:
    s = re.sub(r'(<head[^>]*>)', r'\1\n<meta name="robots" content="noindex, nofollow">', s, count=1)
    p.write_text(s, encoding="utf-8")
    print("confirm: noindex を追加")
EOF
echo "確認用ページをビルドしました"
