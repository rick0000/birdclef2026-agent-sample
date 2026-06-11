---
name: update-knowledge
description: reported状態の実験レポートから知見を抽出し、L1知見ファイル + L2 index追記する。reported → knowledge_updated。
allowed-tools: Bash, Read, Write, Edit, Glob
---

# update-knowledge

`reported` 状態のジョブを1件取り出し、レポートから知見を抽出して knowledge/ に保存する。

## 手順

1. reported状態のジョブを確認する:
```bash
python -m src.tools_for_skills.job_queue list --state reported
```

2. **ジョブがなければ何もせず終了する**

3. ジョブがあれば（1件だけ処理する）:
   a. `reports/<exp_id>_report.md` を読む
   b. `knowledge/experiments/index.md` を読む（あれば。過去の知見サマリを把握するため）

4. **L1: 詳細知見ファイル** を `knowledge/experiments/<exp_id>.md` に書く:

```markdown
# <exp_id> の知見

source: reports/<exp_id>_report.md
analyzed_at: <日時>

## 何をしたか
- <1-2行で>

## 結果
- score: <値>
- 前回比: <改善/悪化/同等>

## 学んだこと
- <箇条書き3-5個>

## 次に試すべきこと
- <具体的な提案（パラメータ値含む）>
```

5. **L2: knowledge/experiments/index.md に1行追記する** （なければ新規作成）:

```markdown
| <exp_id> | <何をしたか1文> | <score> | <前回比> | <日時> |
```

ファイル先頭にヘッダがなければ以下を追加:
```markdown
# 実験知見一覧

| exp_id | 内容 | score | 前回比 | date |
|--------|------|-------|--------|------|
```

6. 遷移する:
```bash
python -m src.tools_for_skills.job_queue transition <exp_id> knowledge_updated
```

## 注意事項

- 1サイクル1件だけ処理する
- `knowledge/` と `knowledge/experiments/` がなければ mkdir する
- L1ファイルに全詳細を書き、L2 indexは1行サマリだけ
- 既存知見と矛盾する場合は index の該当行も修正する
