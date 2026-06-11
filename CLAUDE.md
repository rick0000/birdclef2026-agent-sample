# BirdCLEF2026 Agent Harness

BirdCLEF2026コンペをClaude Codeエージェントで解くプロジェクト。

## アーキテクチャ

### 2層実行モデル

- **Bash層**（決定論的・トークン消費ゼロ）: `scripts/run_next_experiment.sh` が実験を実行し状態遷移する
- **Claude層**（知性が必要な時だけ）: 各スキルが1つの遷移だけ担当する

### 状態遷移

```
not_executed → executing → done → reported → knowledge_updated → completed
                            ↓
                          failed → not_executed（リトライ）
```

| 遷移 | 担当 | モデル |
|------|------|--------|
| not_executed → executing → done/failed | bash | なし |
| done → reported | `/analyze-results` | opus |
| reported → knowledge_updated | `/update-knowledge` | sonnet |
| knowledge_updated → completed + enqueue | `/plan-next` | opus |
| L2→L3 集約 | `/cron-update-whole-report` | sonnet |

#### 提出Notebook作成トラック（状態マシンとは独立）

`completed` 実験の Kaggle 提出用 Notebook 作成は、状態マシンに組み込まず独立トラックで回す。**自動では提出しない**。Kaggle 上にレビュー可能な Notebook を作るところまでが自動で、実際の Submit は人間が確認して手動で行う。

| 役割 | 担当 | モデル |
|------|------|--------|
| どの実験を Notebook 化するか判断 → 起動 | `/decide-submission` | opus |
| Notebook 作成（weights upload → kernel push） | `scripts/push_submission_notebook.sh` (bash) | なし |
| Kaggle 上でレビュー → Submit | **人間（手動）** | — |

push 済み Notebook は `reports/leaderboard.md` に `PENDING_HUMAN_SUBMIT` で記録される。人間が提出して得た Public/Private スコアを同表に追記すると、次サイクルの判断材料になる。kernel の push は提出枠（5回/日）を消費しない。

### 3層ファイル構造（トークン節約）

```
L3: 全体戦略（plan-next はこれだけ読む）
  knowledge/strategy.md

L2: 種目別サマリ index
  reports/index.md
  knowledge/experiments/index.md
  knowledge/resources/index.md

L1: 個別ファイル
  reports/<exp_id>_report.md
  knowledge/experiments/<exp_id>.md
  knowledge/resources/<resource>.md
```

## パス一覧

### 入力（読み取り専用）
- `input/` — コンペデータ
- `input/cache/perch_v2/` — 事前計算済みembedding
- `docs/competition_specification/` — コンペ仕様
- `docs/past_top_solutions/` — 過去上位解法
- `docs/external_knowledge/` — 外部リソース原本

### 実験
- `experiments/exp0000/` — ベースライン（テンプレ、変更しない）
- `experiments/<exp_id>/` — 各実験（train.py, config.json, run.sh, results/, logs/）

### 出力
- `reports/` — L1: 個別レポート + L2: index.md
- `knowledge/` — L1: 個別知見 + L2: index.md + L3: strategy.md
- `docs/whole_report.html` — 人間向け全体ダッシュボード
- `submissions/` — 提出notebook（`/create-submission-notebook <exp_id>` で生成）
- `reports/leaderboard.md` — 提出 worklist / スコア台帳（`push_submission_notebook.sh` が push 時に追記、人間がスコア記入）

### ジョブ管理
- `job_queue/` — 状態別ディレクトリ（job_queue.py が管理）

## 運用

```bash
# Bash層: tmuxの別ペインで実験を回す
bash scripts/run_next_experiment.sh

# Claude層: loopで各遷移を監視
/loop 10m /analyze-results
/loop 10m /update-knowledge
/loop 10m /plan-next
/loop 30m /cron-update-whole-report
/loop 6h /decide-submission   # 提出トラック（独立）。6hに1回、どの実験に提出枠を使うか判断する
```

## 提出Notebook操作

```bash
# （参考）本日の人間の提出枠 残数を確認
python -m src.tools_for_skills.kaggle_submit budget
# 特定実験の Notebook を Kaggle に作成（提出はしない。submissions/<exp_id>.ipynb が必要）
bash scripts/push_submission_notebook.sh <exp_id>
# → 出力された kernel URL を人間が確認 → Run → Submit を手動で行う
```

## キュー操作

```bash
python -m src.tools_for_skills.job_queue list
python -m src.tools_for_skills.job_queue list --state <state>
python -m src.tools_for_skills.job_queue enqueue <exp_id> --config-path <path>
python -m src.tools_for_skills.job_queue transition <exp_id> <target_state>
python -m src.tools_for_skills.job_queue pick-next
```
