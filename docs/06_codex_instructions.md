# Codex向け 実装指示（このまま渡す用）

あなた（Codex）は次を実装してください：

## 1) 実装ゴール
- J-Quants API (V2) を `jquants-api-client` の `jquantsapi.ClientV2` で呼び出し、
  Premiumで取得可能な全データセット（READMEに列挙されたClientV2メソッド群）を
  レート制御しながら網羅取得し、データレイク（bronze/silver）へ保存する。 :contentReference[oaicite:37]{index=37}

## 2) 認証
- `.env` の `JQUANTS_API_KEY` を読み取り、`ClientV2(api_key=...)` で初期化する。 :contentReference[oaicite:38]{index=38}

## 3) 取得対象（最低限）
- Free相当:
  - get_eq_master, get_eq_bars_daily, get_fin_summary, get_eq_earnings_cal :contentReference[oaicite:39]{index=39}
- Light相当:
  - get_idx_bars_daily, get_idx_bars_daily_topix, get_mkt_calendar, get_bulk_list, get_bulk :contentReference[oaicite:40]{index=40}
- Standard相当:
  - get_mkt_short_ratio, get_mkt_short_sale_report, get_mkt_margin_interest, get_mkt_margin_alert,
    get_drv_bars_daily_fut, get_drv_bars_daily_opt, get_drv_bars_daily_opt_225 :contentReference[oaicite:41]{index=41}
- Premium相当（追加）:
  - get_mkt_breakdown, get_eq_bars_daily_am, get_eq_investor_types, get_fin_details, get_fin_dividend :contentReference[oaicite:42]{index=42}

## 4) レート制御・リトライ
- Premiumは 500 req/min。安全側に 480 req/min で制御する。 :contentReference[oaicite:43]{index=43}
- 429時は指数バックオフ。大幅超過を継続すると5分遮断され得るのでクールダウンも実装。 :contentReference[oaicite:44]{index=44}

## 5) ページング
- pagination_key があるAPIは、尽きるまで追う（null/空まで）。 :contentReference[oaicite:45]{index=45}

## 6) データ保存
- bronze: 1ページ=1ファイル（jsonl.gz）
- silver: parquet（dtパーティション）
- 取得パラメータ、run_id、ページング連鎖を manifest.json に記録

## 7) 注意
- `*_range` は内部で多数のリクエストを並列発行し得てレートリミットに達しうるため原則使わない。 :contentReference[oaicite:46]{index=46}
- “銘柄×日付” の直積走査は避ける。可能なAPIは “dateのみで全銘柄取得” を優先する（レートリミットBest Practice）。 :contentReference[oaicite:47]{index=47}

## 8) CLI
- `python -m src.main backfill --from 2006-01-01 --to 2026-01-24`
- `python -m src.main incremental --date 2026-01-24`
- `python -m src.main verify --dataset eq_bars_daily --date 2023-03-24`