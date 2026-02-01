# 全通りリクエスト送信（網羅取得）戦略

## 基本方針
- 「Premiumで取得可能なデータセット = `ClientV2` の該当メソッド群（README記載）」を対象にする。 :contentReference[oaicite:20]{index=20}
- 各データセットについて、API仕様上のパラメータ組み合わせ（例: code/date/from/to/pagination_key）を“取りこぼしなく”走査する。
- ただし、無駄に「銘柄×日付」を直積で回すのは避ける（レートリミットBest Practiceで推奨されない）。 :contentReference[oaicite:21]{index=21}

## 例：株価日足（/v2/equities/bars/daily）
- 仕様より、リクエストは「code または date が必須」。 :contentReference[oaicite:22]{index=22}
- 仕様に列挙される代表的取得パターン： :contentReference[oaicite:23]{index=23}
  1) codeのみ：特定銘柄の全期間
  2) code + date：特定銘柄の特定日
  3) code + from/to：特定銘柄の期間
  4) dateのみ：特定日の全銘柄

### 網羅取得の推奨パス（効率重視）
- **日次バックフィルは (4) dateのみ** を基本にする  
  → “その日付の全銘柄” を1リクエスト（ページングあり）で取れるため。 :contentReference[oaicite:24]{index=24}
- 過去20年（Premium上限）を営業日カレンダーで割り出し、営業日ごとに date=YYYY-MM-DD で取得する。 :contentReference[oaicite:25]{index=25}
- pagination_key が返る場合は最後まで追う。 :contentReference[oaicite:26]{index=26}

### “全通り”の定義（このプロジェクト内）
- データ欠損や仕様変更検知のために、以下を追加で回す：
  - codeのみ（全期間）を「代表銘柄サンプル」で回して、date-only取得と整合するかを監査
  - code + from/to を「代表銘柄サンプル」で回して、ページング境界の挙動を監査
- ただし「全銘柄×全日付」をcode軸で二重に回すことはしない（費用対効果が低い）。

## 例：午前終値（/v2/equities/bars/daily/am）
- 仕様より、codeは任意。指定しない場合は「全銘柄の午前データ」。pagination_keyあり。 :contentReference[oaicite:27]{index=27}
- 注意：当日データは翌日早朝まで取得可能、ヒストリカルは日足を使う旨が明記。 :contentReference[oaicite:28]{index=28}
- 網羅取得：
  - 毎営業日（当日分）に codeなしで取得し、ページングを追う。
  - データレイク側は「スナップショット（その日の午前）」として保存。

## 例：投資部門別（/v2/equities/investor-types）
- 仕様より、「section または from/to」が指定可能。 :contentReference[oaicite:29]{index=29}
- 改定（修正）が起きる可能性があり、PublishedDate等で“改定前/改定後”が併存し得る旨の注意がある。 :contentReference[oaicite:30]{index=30}
- 網羅取得：
  - from/to を週次単位で前進させて全期間を回収
  - 取得結果は “上書き” ではなく “追記（append-only）” で保持し、改定の差分を残す

## ページング一般
- pagination_key が返るAPIは、null/空になるまでループ。
- 各ページを「同一論理取得（dataset, params, run_id）」としてメタデータ連結する。

## `*_range` ユーティリティの扱い
- READMEに「range系は指定範囲に対し並列で繰り返しリクエストするため、広い範囲や短時間連続実行でレートリミット到達しうる」と明記。 :contentReference[oaicite:31]{index=31}
- よって本実装では、原則として `*_range` は使わず、**自前のchunking + レート制御**で逐次取得する。