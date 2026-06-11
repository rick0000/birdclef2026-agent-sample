#!/bin/bash
# upload_experiment_weights.sh — experiments/<exp_id>/outputs/checkpoints/ を
# Kaggle Dataset としてアップロードする。
#
# 使い方:
#   bash scripts/upload_experiment_weights.sh <exp_id>
#
# 前提:
#   - kaggle CLI が設定済み (~/.kaggle/kaggle.json または KAGGLE_USERNAME/KAGGLE_KEY)
#   - experiments/<exp_id>/outputs/checkpoints/ に model.pt と meta.json がある
#
# 出力:
#   Kaggle Dataset: <username>/birdclef2026-<exp_id>-weights
#   既存なら新バージョン、なければ新規作成。
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: bash scripts/upload_experiment_weights.sh <exp_id>" >&2
    exit 1
fi

EXP_ID="$1"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"  # uv run kaggle のため project dir で実行
CKPT_DIR="$PROJECT_ROOT/experiments/$EXP_ID/outputs/checkpoints"
# kaggle CLI は v2.2+ を uv 経由で（PATH の bare kaggle は旧 1.7.x のことがある）
KAGGLE="${KAGGLE:-uv run kaggle}"

if [ ! -d "$CKPT_DIR" ]; then
    echo "ERROR: $CKPT_DIR が存在しません。先に実験を実行してください。" >&2
    exit 1
fi

if [ ! -f "$CKPT_DIR/model.pt" ]; then
    echo "ERROR: $CKPT_DIR/model.pt が見つかりません。" >&2
    exit 1
fi

USER_NAME="${KAGGLE_USERNAME:-}"
if [ -z "$USER_NAME" ] && [ -f "$HOME/.kaggle/kaggle.json" ]; then
    USER_NAME="$(python -c "import json,os;print(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['username'])" 2>/dev/null || true)"
fi
if [ -z "$USER_NAME" ]; then
    USER_NAME="$($KAGGLE config view 2>/dev/null | awk '/username/ {print $NF}')"
fi
if [ -z "$USER_NAME" ]; then
    echo "ERROR: kaggle username が取得できません。kaggle CLI 設定を確認してください。" >&2
    exit 1
fi

DATASET_SLUG="birdclef2026-$EXP_ID-weights"
DATASET_ID="$USER_NAME/$DATASET_SLUG"

cat > "$CKPT_DIR/dataset-metadata.json" <<EOF
{
  "title": "birdclef2026 $EXP_ID weights",
  "id": "$DATASET_ID",
  "licenses": [{"name": "CC0-1.0"}]
}
EOF

# 既存判定: kaggle datasets metadata で取得できるかどうか
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if $KAGGLE datasets metadata -p "$TMP_DIR" "$DATASET_ID" >/dev/null 2>&1; then
    echo "[upload] $DATASET_ID は既存。新バージョンとしてアップロードします。"
    $KAGGLE datasets version -p "$CKPT_DIR" -m "update $EXP_ID weights"
else
    echo "[upload] $DATASET_ID を新規作成します。"
    $KAGGLE datasets create -p "$CKPT_DIR"
fi

echo "[upload] done: $DATASET_ID"
echo "         Kaggle Notebook での参照パス: /kaggle/input/$DATASET_SLUG/"
