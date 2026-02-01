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