---
name: cron-update-whole-report
description: L2 indexファイル群を読んでL3戦略ファイル(strategy.md)と全体レポート(whole_report.html)を更新する。
allowed-tools: Bash, Read, Write, Edit, Glob
---

# cron-update-whole-report

L2 の各 index ファイルを集約して、L3 の戦略ファイルと人間向け全体レポートを更新する。

## 手順

1. L2 index ファイルを読む:
   - `reports/index.md`（実験レポート一覧）
   - `knowledge/experiments/index.md`（実験知見一覧）
   - `knowledge/resources/index.md`（外部リソース知見一覧。あれば）

2. **いずれも存在しない、または前回更新から変化がなければ何もせず終了する**

3. **L3: knowledge/strategy.md を更新する:**

```markdown
# 全体戦略

updated_at: <日時>

## 現在のベストスコア
- exp_id: <best_exp>
- OOF macro AUC: <score>
- method: <手法>

## これまでに分かったこと
- <全実験から得られた主要知見を5-10個>
- <何が効いて何が効かなかったか>

## 未検証のアイデア
- <knowledge/resources や過去実験の提案から、まだ試していないもの>

## 次の方針
- <優先度順で3-5個>
```

4. **docs/whole_report.html を更新する:**
   - L2 index の表を HTML に変換
   - スコア推移グラフ用のデータを含める
   - strategy.md の内容もHTML内に反映する

## 注意事項

- L2 index だけ読む。L1 の個別ファイルは読まない（トークン節約）
- strategy.md は plan-next が唯一の読者。簡潔かつ具体的に書く
- 変化がなければ何もしない（無駄なトークン消費を防ぐ）
