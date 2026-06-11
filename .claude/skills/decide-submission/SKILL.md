---
name: decide-submission
description: completed状態の実験から「どれを Kaggle 上の提出用Notebookにするか」を判断し、価値があれば scripts/push_submission_notebook.sh で Kaggle に kernel を作成する。提出自体はしない（人間が Kaggle 上で確認して手動提出する）。
allowed-tools: Bash, Read, Write, Glob, Grep
---

# decide-submission

`completed` になった実験のうち、**Kaggle 上に提出用 Notebook を用意すべきもの**を判断し、`scripts/push_submission_notebook.sh` で Kaggle に kernel を作成（push）する。

**提出はしない。** Kaggle 上にレビュー可能な Notebook を用意するところで止め、実際の「Submit to Competition」は人間が Kaggle 上で確認してから手動で行う。kernel の push は提出枠（5回/日）を消費しないので枠ガードは不要。

**この skill のミッション**: completed 実験のうち、人間に提出を検討してもらう価値がある（スコア更新が見込める／OOF と Public の乖離を測りたい）ものを選び、Kaggle 上に Notebook を用意して worklist (`reports/leaderboard.md`) に積む。

## 手順

### 1. 現状を読む

```bash
python -m src.tools_for_skills.job_queue list --state completed
cat reports/leaderboard.md 2>/dev/null        # 既に push 済み / スコア記入済みの実験
python -m src.tools_for_skills.kaggle_submit budget   # （参考）本日の人間の提出枠 残数
```

### 2. 未 push の completed 実験を洗い出す

`reports/leaderboard.md` に exp_id の行が**無い**もの = まだ Notebook を Kaggle に用意していない候補。
（`experiments/<exp_id>/outputs/kernel/kernel-metadata.json` の有無でも二重チェックできる。）

候補が無ければ、その旨メモして終了。

### 3. 用意する実験を1つ選ぶ（しないことも選択肢）

各候補の OOF スコアを読む:

```bash
python -c "import json; d=json.load(open('experiments/<exp_id>/outputs/results/result.json')); print(d['metrics']['oof_macro_auc'])"
```

判断材料（固定ルールにしない。その都度判断する）:
- OOF macro AUC が leaderboard.md の既知スコア群の **ベストを更新しそうか**。
- まだ Public スコアの実測が1本も無いなら、**OOF↔Public の対応関係を測る**価値が高い（最初の1本は積極的に用意してよい）。
- 明確に劣る実験・微差の実験には kernel を作らない（人間のレビュー負荷を上げない）。

→ **用意する1本を決める**。価値ある候補が無ければ「今回は用意しない」と判断して理由をメモし終了。

### 4. 推論Notebookを用意する（ローカル）

push には `submissions/<exp_id>.ipynb` が必要:

```bash
ls submissions/<exp_id>.ipynb 2>/dev/null
```

- 既に存在すれば次へ。
- 無ければ **create-submission-notebook の手順に従って生成する**（`experiments/<exp_id>/train.py` / `config.json` / `outputs/checkpoints/meta.json` を読み、推論用 Notebook を `submissions/<exp_id>.ipynb` に書き出す）。生成できない前提不足があれば中止しメモして終了。

### 5. Kaggle に Notebook を作成する（push のみ・提出しない）

`scripts/push_submission_notebook.sh` は weights アップロード → kernel-metadata 生成 → `kaggle kernels push` を行い、`reports/leaderboard.md` に `PENDING_HUMAN_SUBMIT` で1行追記する。weights アップロードに時間がかかるため **run_in_background で起動し、完了を待たない**:

```bash
bash scripts/push_submission_notebook.sh <exp_id>
```

（Bash ツールの `run_in_background: true` で起動すること。）

### 6. 報告

ユーザー（ログ）に以下を伝える:
- Kaggle 上に Notebook を用意した exp_id とその理由（または「今回は用意しない」判断の理由）
- **人間が行う次のステップ**: Kaggle で当該 Notebook (`https://www.kaggle.com/code/<user>/birdclef2026-<exp_id>-sub`) を開いて確認 → Run → Submit to Competition。提出後の Public/Private スコアを `reports/leaderboard.md` の該当行に追記すると、次サイクルの判断材料になる。

## 注意事項

- **提出は絶対にしない**。この skill と `push_submission_notebook.sh` は Kaggle 上に Notebook を作るだけ。`kaggle competitions submit` は実行しない。
- **1サイクルで用意するのは最大1本**。人間のレビュー負荷を抑える。
- push 処理自体（weights upload / kernel push）は `scripts/push_submission_notebook.sh`（bash・決定論的）の責務。この skill は **判断と起動だけ**。
