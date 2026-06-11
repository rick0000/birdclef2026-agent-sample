---
name: analyze-results
description: done状態の実験結果を分析し、L1詳細レポート生成 + L2 index追記する。done → reported。
allowed-tools: Bash, Read, Write, Edit, Glob
---

# analyze-results

`done` 状態のジョブを1件取り出し、result.json, per_class_metrics.csv, train.py, config.json を分析して詳細レポートを生成する。

## 手順

1. done状態のジョブを確認する:
```bash
python -m src.tools_for_skills.job_queue list --state done
```

2. **ジョブがなければ何もせず終了する**

3. ジョブがあれば（1件だけ処理する）:
   a. `experiments/<exp_id>/outputs/results/result.json` を読む
   b. `experiments/<exp_id>/outputs/results/per_class_metrics.csv` があれば読む
   c. `experiments/<exp_id>/config.json` を読む
   d. `experiments/<exp_id>/train.py` を読む

4. **L1: 詳細レポート** を `reports/<exp_id>_report.md` に書く:

```markdown
# <exp_id> 実験レポート

generated_at: <日時>

## 設定
- method: <手法>
- params: <主要パラメータ>

## 結果
| メトリクス | 値 |
|---|---|
| OOF macro AUC | ... |
| loss | ... |

## 学習履歴
<epoch_historyがあれば傾向を記述>

## クラス別分析
<per_class_metricsがあればワースト/ベストクラスを報告>

## 所見
- <今後の学習戦略に関わるものをすべて箇条書き>
```

5. **L2: reports/index.md に1行追記する** （なければ新規作成）:

```markdown
| <exp_id> | <method> | <CV split method> | <OOF AUC> | <主な所見を1文で> | <日時> |
```

ファイル先頭にヘッダがなければ以下を追加:
```markdown
# 実験レポート一覧

| exp_id | method | CV split method | OOF AUC | 所見 | date |
|--------|--------|----------------|---------|------|------|
```

6. 遷移する:
```bash
python -m src.tools_for_skills.job_queue transition <exp_id> reported
```

## 注意事項

- 1サイクル1件だけ処理する
- `reports/` がなければ mkdir する
- L1レポートは詳細に書くこと。後続の実験指針になる重要なドキュメント。分析に基づく所見を必ず入れること。
- CV split methodを変更する場合は過去のスコアが直接比較できないため、method名に明記すること（例: "perch_v2_embedding + attention_pooling (fold CV)" vs "perch_v2_embedding + attention_pooling (random CV)"）