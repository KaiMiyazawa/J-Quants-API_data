以下は、**`J-Quants/jquants-api-client-python`（`jquants-api-client`）を前提**に、Premiumプランで取得可能なデータを漏れなくダウンロードしてデータレイク化するための「Codex向けコンテキストMarkdown群（設計書一式）」です。
※J-Quants APIは **V2が2025-12-22にリリース**され、移行が推奨されています。 ([JPX Quants][1])
※Premiumのレートリミットは **500 req/min**、超過時は **HTTP 429**、大幅超過を継続すると **約5分遮断**の可能性があります。 ([JPX Quants][2])
※`jquants-api-client` READMEに、V2で使えるラッパー（メソッド）一覧が明記されています（Premium対象も含む）。 ([GitHub][3])

---

## `00_project_overview.md`

```md
# J-Quants Premium 全量取得 → データレイク構築プロジェクト（V2 / jquants-api-client 前提）

## 目的
- J-Quants API（Premiumプラン）で取得可能なデータを網羅的に取得し、ローカル（またはクラウド）にデータレイクとして保存する。
- 初回は「過去データのバックフィル（可能な範囲の全量）」を実施し、以後は日次・週次で増分更新する。

## 前提（重要）
- 実装は J-Quants 公式Pythonクライアント `jquants-api-client`（GitHub: J-Quants/jquants-api-client-python）を使用する。
  - V2は APIキー方式（x-api-key）で認証する。`ClientV2` を使用する。READMEにサンプルあり。 :contentReference[oaicite:3]{index=3}
- J-Quants APIはV1→V2へ移行中。V2は2025-12-22リリース。 :contentReference[oaicite:4]{index=4}
- V2 Premiumの過去データ取得可能期間は「最大過去20年」。 :contentReference[oaicite:5]{index=5}
- Premiumのレートリミットは 500 requests / minute。429 Too Many Requests時は待機＆リトライが必要。大幅超過を継続すると約5分遮断の可能性。 :contentReference[oaicite:6]{index=6}

## 成果物
1. 全API（Premiumで利用可能な全データセット）の網羅取得ジョブ
2. データレイク（Bronze: Raw / Silver: 正規化）ディレクトリ設計
3. メタデータ（取得日時・パラメータ・ページングキー・ジョブバージョン）設計
4. レートリミット・リトライ・再開（checkpoint）設計
5. `.env` / `venv` / `requirements.txt` を含む実行環境一式

## 非目標
- 分析基盤（クエリエンジン、カタログ、データウェアハウス統合）は本プロジェクトの次段階。
- 取得データの投資判断モデル化は別プロジェクト。
```

---

## `01_environment_setup.md`

````md
# 実行環境（venv / .env / requirements.txt）

## venv
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
python -m pip install --upgrade pip
pip install -r requirements.txt
````

## .env（例）

* APIキーは `.env` に保存し、`python-dotenv` でロードする。
* 公式クライアントも `${JQUANTS_API_KEY}` を読めるが、明示的に `.env` をロードしてから `ClientV2(api_key=...)` へ渡す方針にする（実行環境差異を減らす）。

```env
JQUANTS_API_KEY=xxxxxxxxxxxxxxxxxxxx

# 保存先（ローカル例）
DATA_LAKE_ROOT=./data_lake

# 実行制御
MAX_REQ_PER_MIN=480          # Premium上限500に対して安全側に倒す
HTTP_TIMEOUT_SEC=60
MAX_RETRY=8
RETRY_BASE_SLEEP_SEC=2
CHECKPOINT_DB=./run/checkpoints.sqlite
LOG_LEVEL=INFO
```

## requirements.txt（例）

* `jquants-api-client` はPyPIで提供（例: 1.9.0 が公開されている）。 ([PyPI][4])

```txt
jquants-api-client>=1.9.0
python-dotenv>=1.0.0
tenacity>=8.2.3
pandas>=2.0.0
pyarrow>=14.0.0
orjson>=3.9.0
requests>=2.31.0
tqdm>=4.66.0
SQLAlchemy>=2.0.0
```

## リポジトリ構成（提案）

```text
.
├── README.md
├── requirements.txt
├── .env                  # gitignore
├── .gitignore
├── .venv/                # ローカル
├── src/
│   ├── main.py
│   ├── config.py
│   ├── jquants_client.py
│   ├── rate_limit.py
│   ├── checkpoints.py
│   ├── datasets/
│   │   ├── equities.py
│   │   ├── markets.py
│   │   ├── indices.py
│   │   ├── derivatives.py
│   │   ├── fins.py
│   │   └── bulk.py
│   └── storage/
│       ├── bronze.py
│       ├── silver.py
│       └── manifest.py
└── run/
    ├── logs/
    └── checkpoints.sqlite
```

````

---

## `02_jquants_v2_and_client_mapping.md`

```md
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
````

---

## `03_request_enumeration_strategy.md`

```md
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
```

---

## `04_rate_limit_retry_checkpoint.md`

```md
# レートリミット / リトライ / 再開（checkpoint）設計

## レートリミット（Premium）
- 500 requests / minute :contentReference[oaicite:32]{index=32}
- 超過時：HTTP 429 Too Many Requests :contentReference[oaicite:33]{index=33}
- 大幅超過を継続：5分程度の完全遮断が起こり得る :contentReference[oaicite:34]{index=34}

## クライアント側制御（必須）
- トークンバケット（1分窓）またはリーキーバケットで 480 req/min 程度に抑制
- 429時は即リトライ禁止。指数バックオフ + ジッタ：
  - sleep = min(max_sleep, base * 2^n + random(0,1))
- 429が続く場合は “遮断状態” を疑い、5分程度のクールダウンを許容する。 :contentReference[oaicite:35]{index=35}

## Checkpoint（再開）必須要件
- データセット単位・パラメータ単位で「どこまで取得したか」を永続化
- 例（株価日足 date-only）：
  - dataset = eq_bars_daily
  - date = 2023-03-24
  - pagination_key = "value1.value2."
  - status = in_progress / done / failed
- 保存先：SQLite（例: `run/checkpoints.sqlite`）
- ジョブ再実行時：
  - doneはスキップ
  - in_progress/failedは pagination_key から再開

## 監査ログ（推奨）
- 1リクエストごとに
  - endpoint（またはclient method）
  - params（正規化JSON）
  - HTTP status
  - response bytes
  - retry_count
  - elapsed_ms
  - run_id
- を記録する（後日の欠損・API変更の調査に必須）。
```

---

## `05_data_lake_layout.md`

```md
# データレイク設計（Bronze / Silver）

## 基本思想
- Bronze（Raw）: APIレスポンスを「可能な限り生」で保存（JSON Lines / gzip推奨）
- Silver（Normalized）: DataFrame化してスキーマ正規化、パーティション最適化（Parquet推奨）

## 推奨ディレクトリ（例）
DATA_LAKE_ROOT/
  bronze/
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/                # 取得対象日（or 取得窓の開始日）
        run_id=<uuid>/
          page=000001.jsonl.gz
          page=000002.jsonl.gz
          manifest.json
  silver/
    dataset=<dataset_name>/
      dt=<YYYY-MM-DD>/
        part-0000.parquet
        _schema.json
  metadata/
    runs/
      run_id=<uuid>.json
    checkpoints.sqlite

## manifest.json（例）
- dataset
- client_method
- request_params_hash
- started_at / finished_at
- pages
- row_count_estimate
- pagination_chain
- warnings（例：429発生回数）

## “改定が起こりうるデータ”の扱い
- 投資部門別のように、修正履歴があり得る（改定前後が提供され得る）旨が仕様で注意されている。 :contentReference[oaicite:36]{index=36}
- 上書きせず append-only で保持し、（StartDate, EndDate, Section, PublishedDate等）でバージョニングできるようにする。
```

---

## `06_codex_instructions.md`

```md
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
```

---

## `07_appendix_known_specs_examples.md`

```md
# 付録：取得仕様の具体例（取得設計に直接使う）

## 株価日足 /v2/equities/bars/daily（代表例）
- code または date が必須 :contentReference[oaicite:48]{index=48}
- 代表パターン：
  - codeのみ（全期間）
  - code + date（単日）
  - code + from/to（期間）
  - dateのみ（単日・全銘柄） :contentReference[oaicite:49]{index=49}
- レスポンス項目例（Date, Code, O/H/L/C, Vo, Va, Adj* など）。午前/午後項目はPremium限定の説明あり。 :contentReference[oaicite:50]{index=50}

## 午前終値 /v2/equities/bars/daily/am
- codeは任意。未指定なら全銘柄。pagination_keyあり。 :contentReference[oaicite:51]{index=51}
- 当日データの取得可能期限（翌日早朝まで）や、ヒストリカルは日足を使う注意あり。 :contentReference[oaicite:52]{index=52}

## 投資部門別 /v2/equities/investor-types
- section または from/to を指定可能。 :contentReference[oaicite:53]{index=53}
- 改定時に改定前後が併存し得る注意があり、PublishedDate 等で識別可能な旨が書かれている。 :contentReference[oaicite:54]{index=54}

## V2移行時の主要対応（参考）
- migration表に、V1→V2のエンドポイント対応と、V2のレートリミット表がある。 :contentReference[oaicite:55]{index=55}
```

---

# 補足（重要な設計判断）

* あなたの要件「**Premiumで取れるデータ全部を最新でダウンロード**」に対して、実務上の“網羅”は **(A) データセット網羅** と **(B) 時系列網羅（取りうる全期間＋増分）** が支配的です。
  そのため上記mdでは、**“全通り＝全パラメータ直積”** ではなく、仕様が許すなら **date-onlyで全銘柄** のような効率パスを主軸にして、監査目的で一部サンプルパスを追加する設計に寄せています。これはレートリミットBest Practice（無駄リクエスト回避、バルク活用）にも整合します。 ([JPX Quants][2])

---

必要なら、次のステップとして「**上記md群に合わせた実コード雛形（src/一式）**」も、`jquants-api-client` のメソッド名・ページング・checkpoint・jsonl.gz/parquet出力まで含めてこちらで生成できます。

[1]: https://jpx-jquants.com/en/spec "About J-Quants API - J-Quants API Reference"
[2]: https://jpx-jquants.com/ja/spec/rate-limits?utm_source=chatgpt.com "レートリミットについて - Protocol API Reference"
[3]: https://github.com/J-Quants/jquants-api-client-python "GitHub - J-Quants/jquants-api-client-python"
[4]: https://pypi.org/project/jquants-api-client/?utm_source=chatgpt.com "jquants-api-client · PyPI"

