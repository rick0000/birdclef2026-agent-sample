---
name: create-submission-notebook
description: 指定された実験ID(exp_id)のtrain.pyとconfigを読んで、Kaggle提出用の推論Notebookを生成する。重みは事前に scripts/upload_experiment_weights.sh で Kaggle Dataset 化されている前提。手動で呼び出して使う。
argument-hint: <exp_id>
allowed-tools: Bash, Read, Write, Glob, Grep
---

# create-submission-notebook

引数で指定された実験(`<exp_id>`)の **Kaggle提出用 推論Notebook** を生成する。

## 入力
- `$ARGUMENTS`: `<exp_id>` (例: `exp0000`)

## 前提
- `experiments/<exp_id>/train.py` が存在し、実行済みで `outputs/checkpoints/{model.pt, meta.json}` を保存している
- `bash scripts/upload_experiment_weights.sh <exp_id>` で重みが Kaggle Dataset (`birdclef2026-<exp_id>-weights`) としてアップロード済み

前提が満たされていない場合は、ユーザーに不足を報告して中断する（Notebookを生成しない）。

## 出力
- `submissions/<exp_id>.ipynb` (Kaggle提出用 推論Notebook)

## 手順

### 1. 入力確認

以下を順に確認する。1つでも欠けていればユーザーに報告して中断:

```bash
ls experiments/<exp_id>/train.py
ls experiments/<exp_id>/config.json
ls experiments/<exp_id>/outputs/checkpoints/model.pt
ls experiments/<exp_id>/outputs/checkpoints/meta.json
```

### 2. 入力を読み込む

- `experiments/<exp_id>/train.py` をRead（前処理・モデル定義・推論ロジックを把握）
- `experiments/<exp_id>/config.json` をRead（手法の概要）
- `experiments/<exp_id>/outputs/checkpoints/meta.json` をRead（labels, embedding_dim等）
- `experiments/<exp_id>/outputs/results/result.json` をRead（CVスコアをNotebook冒頭に記載）

### 3. Notebookセル構成を組み立てる

以下のセル順序で生成する:

| # | type | 内容 |
|---|------|------|
| 1 | markdown | 実験ID / description / OOF AUC / 使用Dataset名 |
| 2 | code | imports（train.py からコピペ流用。Kaggle環境にない依存があれば先頭に `!pip install`） |
| 2.5 | code | **環境判定 + パス定義**（下記「パス解決」参照。`IS_KAGGLE` で Kaggle/ローカルを切り替え、固定パスを使う。glob 探索はしない） |
| 3 | code | 定数定義（`N_CLASSES`, `PRIMARY_LABELS`, `EMBEDDING_DIM` 等。`PRIMARY_LABELS` は `sample_submission.csv` の列順から導出する＝学習時と同一で列順ズレを防げる） |
| 4 | code | モデル定義（train.py から `nn.Module` / `nn.Linear` 等のクラス・関数定義をコピペ。学習専用のロジックは含めない） |
| 5 | code | 前処理関数定義（embedding計算 or 既存特徴量の読み込み。train.py の前処理パイプラインを推論用に組み替えてコピペ） |
| 6 | code | 重みロード（`WEIGHTS_PATH`、下記パス参照） |
| 7 | code | 推論ループ（`TEST_AUDIO_DIR` 配下の音声を列挙し、**5秒チャンクごと**に予測。`row_id = <音声stem>_<終了秒>`。soundscape は 60s → 12 行） |
| 8 | code | `submission.csv` 出力（`row_id, <label1>, <label2>, ...` 形式。列順は `sample_submission.csv` に厳密一致。test が空でもヘッダ付きで出力する） |

#### パス解決（重要・glob 探索はしない）

`kaggle kernels push`（CLI）で作成した kernel のマウント構成は **UI 追加時と異なる**:

| 種別 | マウントパス |
|------|--------------|
| コンペデータ | `/kaggle/input/competitions/birdclef-2026/` |
| 他者の Dataset (perch 等) | `/kaggle/input/datasets/<owner>/<slug>/` |
| 自分の Dataset (weights) | `/kaggle/input/<slug>/` （フラット） |

環境変数で判定して固定パスを切り替える（`scripts/push_submission_notebook.sh` が CLI push する前提）:

```python
import os
from pathlib import Path
IS_KAGGLE = os.environ.get('KAGGLE_KERNEL_RUN_TYPE') is not None
if IS_KAGGLE:
    COMP_DIR = Path('/kaggle/input/competitions/birdclef-2026')
    WEIGHTS_PATH = Path('/kaggle/input/birdclef2026-<exp_id>-weights/model.pt')
    PERCH_DIR = Path('/kaggle/input/datasets/rishikeshjani/perch-onnx-for-birdclef-2026')
else:
    COMP_DIR = Path('input')
    WEIGHTS_PATH = Path('experiments/<exp_id>/outputs/checkpoints/model.pt')
    PERCH_DIR = Path('input/perch_v2')
SAMPLE_SUB_PATH = COMP_DIR / 'sample_submission.csv'
TEST_AUDIO_DIR = COMP_DIR / 'test_soundscapes'
```

#### Perch 埋め込みを使う実験の注意

- 公開 Dataset `perch-onnx-for-birdclef-2026` に含まれるのは **`perch_v2.onnx`（フル版）** と onnxruntime wheel。`perch_v2_embedding_only.onnx` はローカル限定なので Kaggle では使わない。
- `perch_v2.onnx` は複数出力（embedding/label等）。**`'embedding'` 出力だけ**を `sess.run(['embedding'], ...)` で要求する。入力は `inputs` shape `[batch, 160000]`(=5s@32kHz, 末尾ゼロパディング)、出力 `embedding [batch, 1536]`。
- onnxruntime は Kaggle 標準にない場合があるので、`PERCH_DIR` 内の wheel を `pip install --no-index` する（先頭で `try: import onnxruntime` → 失敗時のみ）。
- `push_submission_notebook.sh` の `EXTRA_DATASETS` で perch Dataset を attach 済みである前提。
- **推論はチャンク単位**（mean pool は学習クリップ用。soundscape の各 5s 行を個別に予測する）。

### 4. 実装方針

- **train.py の "学習用ロジック"（StratifiedKFold, OOF集計, 学習ループ等）はコピペしない**。推論Notebookには不要。
- **モデル定義・前処理関数だけ抽出してコピペ**する。Claude が train.py を理解した上で書き起こす。
- Notebook は `nbformat==4, nbformat_minor==5` の JSON として `Write` ツールで直接生成する。Pythonヘルパは使わない。

### 5. ipynb の最小スキーマ

```json
{
  "cells": [
    {"cell_type": "markdown", "metadata": {}, "source": ["..."]},
    {"cell_type": "code", "metadata": {}, "execution_count": null, "outputs": [], "source": ["..."]}
  ],
  "metadata": {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"}
  },
  "nbformat": 4,
  "nbformat_minor": 5
}
```

`source` は文字列リスト（行末に `\n` を含める）。

### 6. 簡易バリデーション

生成後に以下を確認:

```bash
python -c "import nbformat; nb = nbformat.read('submissions/<exp_id>.ipynb', as_version=4); assert any(c.cell_type=='code' for c in nb.cells); assert any('submission.csv' in ''.join(c.source) for c in nb.cells if c.cell_type=='code')"
```

エラーが出た場合は修正して再生成する。

### 7. 完了報告

ユーザーに以下を伝える:

- 生成パス: `submissions/<exp_id>.ipynb`
- 参照しているKaggle Dataset: `birdclef2026-<exp_id>-weights`
- 手動で行うべき次のステップ:
  1. Kaggleにnotebookをアップロード（Web UI または `kaggle kernels push`）
  2. Datasets / Competition data を attach
  3. Run all → Submit to Competition

## 注意事項

- **1スキル呼び出しで1実験のみ** Notebookを生成する
- 既存の `submissions/<exp_id>.ipynb` がある場合は上書きする（ユーザーが明示的に呼び出している前提）
- `submissions/` ディレクトリが無ければ `mkdir -p submissions` で作成
- BirdCLEF2026 のsample_submission形式（`row_id` + クラス確率カラム）に厳密に従うこと。間違えると提出時にスコアが0になる
