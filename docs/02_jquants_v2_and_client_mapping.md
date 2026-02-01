# J-Quants V2 と `jquants-api-client` の対応（Premium網羅の基準表）

## 認証
- V2は APIキー方式（`x-api-key`） :contentReference[oaicite:8]{index=8}
- `jquants-api-client` は `ClientV2` を提供し、サンプルがREADMEにある。 :contentReference[oaicite:9]{index=9}
- APIキーの設定は、環境変数 `${JQUANTS_API_KEY}` などからも読める（読み込み優先順位がREADMEに記載）。 :contentReference[oaicite:10]{index=10}

## レートリミット（Premium）
- 500 requests / minute :contentReference[oaicite:11]{index=11}
- 429発生時は待機して再試行。大幅超過を継続すると5分程度遮断され得る。 :contentReference[oaicite:12]{index=12}

## V2のレスポンス概形
- 多くのAPIが `{ "data": [...], "pagination_key": "..." }` を返しうる。 :contentReference[oaicite:13]{index=13}
- pagination_key がある場合は、次ページ取得に利用する。 :contentReference[oaicite:14]{index=14}

## 公式クライアント `ClientV2` で利用可能なメソッド一覧（README準拠）
> この一覧を「網羅取得の対象集合（source of truth）」として扱う。 :contentReference[oaicite:15]{index=15}

### Free plan or higher
- get_eq_master（上場銘柄一覧）
- get_eq_bars_daily（株価日足）
- get_fin_summary（決算サマリー）
- get_eq_earnings_cal（決算発表日）

### Light plan or higher
- get_idx_bars_daily（指数日足）
- get_idx_bars_daily_topix（TOPIX日足）
- get_mkt_calendar（営業日カレンダー）
- get_bulk_list（バルクデータ一覧）
- get_bulk（バルクデータ取得）

### Standard plan or higher
- get_mkt_short_ratio（空売り比率）
- get_mkt_short_sale_report（空売り報告）
- get_mkt_margin_interest（週次信用取引残高）
- get_mkt_margin_alert（信用規制情報）
- get_drv_bars_daily_fut（先物日足）
- get_drv_bars_daily_opt（オプション日足）
- get_drv_bars_daily_opt_225（日経225オプション日足）

### Premium plan or higher（本プロジェクトの追加対象）
- get_mkt_breakdown（売買内訳）
- get_eq_bars_daily_am（株価午前終値）
- get_eq_investor_types（投資部門別売買状況）
- get_fin_details（財務詳細）
- get_fin_dividend（配当情報）

### Minute Bar Addon（契約している場合のみ）
- get_eq_bars_minute（分足）
- get_eq_bars_5minute（5分足：分足から算出）
- get_eq_bars_15minute（15分足：分足から算出）

### ユーティリティ（メタデータ系）
- get_market_segments（市場区分一覧）
- get_17_sectors（17業種一覧）
- get_33_sectors（33業種一覧）

### ユーティリティ（日付範囲一括。内部で繰り返しリクエストする点に注意）
- get_list（銘柄一覧：セクター情報付き）
- get_eq_bars_daily_range（株価日足：範囲指定）
- get_fin_summary_range（決算サマリー：範囲指定）
- （READMEには range系があり、広い範囲は並列で多数のAPI呼び出しになりレートリミット到達の恐れが明記） :contentReference[oaicite:16]{index=16}

## V1→V2 主要エンドポイント対応（参考）
- 例：株価日足 `/v1/prices/daily_quotes` → `/v2/equities/bars/daily` :contentReference[oaicite:17]{index=17}
- 例：午前終値 `/v1/prices/prices_am` → `/v2/equities/bars/daily/am` :contentReference[oaicite:18]{index=18}
- 例：投資部門別 `/v1/markets/trades_spec` → `/v2/equities/investor-types` :contentReference[oaicite:19]{index=19}
（他もmigration表に記載あり）