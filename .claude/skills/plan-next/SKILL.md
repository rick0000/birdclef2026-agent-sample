---
name: plan-next
description: knowledge_updated状態の実験を完了させ、L3戦略ファイルに加え、必要に応じてL2/L1ファイルを読んで次の実験を計画・実装・enqueueする。
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# plan-next

`knowledge_updated` 状態のジョブを `completed` に遷移させ、L3戦略ファイルに加え、必要に応じてL2/L1ファイルを読んで次の実験を計画・実装・enqueue する。

**この skill のミッション**: ベースラインに引きずられた小さなパラメータ変更ではなく、**成功確率 20〜60% / 当たれば効果量の大きい構造的変更**を優先して提案する。安全策ばかり積んでも局所最適にハマる。

## 手順

### 1. 完了処理

```bash
python -m src.tools_for_skills.job_queue list --state knowledge_updated
```

knowledge_updated のジョブがあれば completed に遷移する:
```bash
python -m src.tools_for_skills.job_queue transition <exp_id> completed
```

### 2. 次の実験を計画する
L3戦略ファイルを読む:
a. `knowledge/strategy.md` を読む（なければベースラインのみの状態として扱う）

L1/L2ファイルを必要に応じて読む。
a-1. L2: 種目別サマリ index
  reports/index.md
  knowledge/experiments/index.md
  knowledge/resources/index.md

a-2. L1: 個別ファイル
  reports/<exp_id>_report.md
  knowledge/experiments/<exp_id>.md
  knowledge/resources/<resource>.md

b. 次の exp_id を決める:
```bash
ls experiments/
```

c. **候補を 3〜5 件ブレストする**（必ずブレストしてから選ぶ。最初に思いついたものに飛びつかない）

各候補について以下を見積もる:
- **成功確率**: ベストスコアを更新する確率（過去の知見・類似手法の効きやすさ・ベースラインとの距離から推定）
- **効果量**: 当たった場合の AUC リフト見込み（小: <+0.001 / 中: +0.001〜+0.005 / 大: >+0.005）
- **カテゴリ**: 下記のどの軸の変更か

**選定ルール（厳守）:**
1. **成功確率 20〜60%** の候補だけを残す
   - 60%超 = 安全すぎる。ベースラインの延長で局所最適に向かう
   - 20%未満 = 宝くじ。学びが薄い
2. 残った候補のうち **効果量「中」以上** を優先
3. **直近 3 実験のカテゴリ分布を見る**（exp_id 降順で config.json の description を確認）。同じカテゴリ（例: pooling 系）が 2 連続していたら、別カテゴリを優先する
4. **train.py のロジックに手が入る案を選ぶ**

**構造的変更のカテゴリ（発想の枠を広げる用）:**
- **CV 設計**: 分割粒度を変える（recording-level / site-level / time-based / class-stratified の組み合わせ）。希少クラスを test 側に偏らせない工夫など
- **表現**: 別 embedding モデル併用、複数 embedding fusion、時間軸 attention、segment-level → clip-level の集約方法変更
- **損失**: distillation, contrastive, ArcFace 系 metric learning, label smoothing × class-balanced の組み合わせ
- **アーキテクチャ**: 2-stage 分類器（rare/common ルーティング）、prototype head、kNN head、set transformer
- **データ**: pseudo-labeling、soundscape mining、embedding-space mixup、強い augmentation
- **訓練手順**: multi-task（secondary labels 同時予測）、self-supervised pretraining、curriculum learning
- **後処理**: temperature scaling、クラス別 calibration、test-time augmentation

d. 選んだ案を 1 つに絞る。**選定理由を頭の中で言語化**: 「成功確率 X%、効果量 中、カテゴリ Y、直近は Z カテゴリが続いていたので転換」

### 4. 実験を実装する

a. ベースラインをコピーする（**`&&` で他コマンドと連結しない**。連結すると許可スコープが広がり許可ダイアログで止まる。確認用の `ls` などは別コマンドで実行する）:
```bash
cp -r experiments/exp0000 experiments/<exp_id>
```
b. `experiments/<exp_id>/train.py` を編集:
   - EXP_ID を更新
   - 計画に基づきロジックを変更（**train.py に手を入れることを躊躇しない**）

c. `experiments/<exp_id>/config.json` を編集:
   - experiment_id を更新
   - description に **「何を / なぜ / 想定される効きどころ」** を 1 行で記述
   - script パスを更新
   - params に変更内容を記述（構造的変更の場合は「key: 新方式名」で十分。詳細は train.py で）

d. 構文チェック:
```bash
python -c "import ast; ast.parse(open('experiments/<exp_id>/train.py').read())"
```

### 5. enqueue

```bash
python -m src.tools_for_skills.job_queue enqueue <exp_id> --config-path experiments/<exp_id>/config.json
```

### 6. 確認

```bash
python -m src.tools_for_skills.job_queue list
```

## 注意事項

- **1サイクルで1実験だけ** 計画・実装・enqueue する
- **1実験1テーマ**: 1 つの仮説を検証する単位にまとめる。テーマが構造変更なら関連する複数箇所の修正は OK（例: CV 切り方を変えるなら fold 生成と evaluation の両方を触る）
- ベースライン `experiments/exp0000/` は変更しない
