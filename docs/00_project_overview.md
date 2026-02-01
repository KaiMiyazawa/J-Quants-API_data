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