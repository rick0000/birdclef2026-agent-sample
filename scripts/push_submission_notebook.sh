#!/bin/bash
# push_submission_notebook.sh — 指定実験の推論Notebookを Kaggle 上に kernel として作成(push)する。
#
# 提出はしない。Kaggle 上にレビュー可能な Notebook を用意するところで止める。
# 実際の「Submit to Competition」は人間が Kaggle 上で確認してから手動で行う。
# kernel の push は提出枠(5回/日)を消費しないので枠ガードは不要。
#
# 決定論的。Claude不要・トークン消費ゼロ。weights アップロードに時間がかかる程度。
#
# 使い方:
#   bash scripts/push_submission_notebook.sh <exp_id>
#
# 前提:
#   - submissions/<exp_id>.ipynb が生成済み (/create-submission-notebook)
#   - experiments/<exp_id>/outputs/checkpoints/{model.pt,meta.json} が存在
#   - kaggle CLI 設定済み (~/.kaggle/kaggle.json または KAGGLE_USERNAME/KAGGLE_KEY)
#
# 環境変数 (任意):
#   ENABLE_GPU             kernel で GPU を使う (既定 false)
#                          ※BirdCLEF2026 は GPU 提出が無効(runtime 1分のみ)。CPU<=90分が正。
#                          通常は false のままにすること。
#   FORCE_WEIGHTS_UPLOAD   1 なら毎回 weights を再アップロード (既定: 無ければアップロード)
#
# 出力:
#   Kaggle kernel: <username>/birdclef2026-<exp_id>-sub （人間がレビュー→提出）
#   reports/leaderboard.md に1行追記（status=PENDING_HUMAN_SUBMIT。Public/Private は人間が記入）
#   experiments/<exp_id>/outputs/logs/push_<ts>.log にログ
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: bash scripts/push_submission_notebook.sh <exp_id>" >&2
    exit 1
fi

EXP_ID="$1"
COMPETITION="birdclef-2026"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# BirdCLEF2026 は GPU 提出が runtime 1分のみで実質不可。CPU(<=90分)が前提なので既定 false。
ENABLE_GPU="${ENABLE_GPU:-false}"
# 推論に必要な追加 Dataset（カンマ区切り）。Perch 埋め込み ONNX 等。
EXTRA_DATASETS="${EXTRA_DATASETS:-rishikeshjani/perch-onnx-for-birdclef-2026}"
# kaggle CLI は v2.2+ を uv 経由で使う（PATH の bare kaggle は旧 1.7.x のことがある）
KAGGLE="${KAGGLE:-uv run kaggle}"

NOTEBOOK="submissions/$EXP_ID.ipynb"
CKPT_DIR="experiments/$EXP_ID/outputs/checkpoints"
RESULTS_DIR="experiments/$EXP_ID/outputs/results"
LOG_DIR="experiments/$EXP_ID/outputs/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/push_${TIMESTAMP}.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[push:$EXP_ID] $*"; }

# ── 1. 前提チェック ────────────────────────────────────────
if [ ! -f "$NOTEBOOK" ]; then
    log "ERROR: $NOTEBOOK がありません。先に /create-submission-notebook $EXP_ID を実行してください。"
    exit 1
fi
if [ ! -f "$CKPT_DIR/model.pt" ]; then
    log "ERROR: $CKPT_DIR/model.pt がありません。実験が未実行です。"
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
    log "ERROR: kaggle username が取得できません。kaggle CLI 設定を確認してください。"
    exit 1
fi

# ── 2. weights を Kaggle Dataset として用意 ───────────────
WEIGHTS_DATASET="$USER_NAME/birdclef2026-$EXP_ID-weights"
UPLOADED=0
if [ "${FORCE_WEIGHTS_UPLOAD:-0}" = "1" ]; then
    log "weights を強制再アップロードします。"
    bash scripts/upload_experiment_weights.sh "$EXP_ID"
    UPLOADED=1
elif ! $KAGGLE datasets metadata -p "$(mktemp -d)" "$WEIGHTS_DATASET" >/dev/null 2>&1; then
    log "weights dataset が未作成のためアップロードします: $WEIGHTS_DATASET"
    bash scripts/upload_experiment_weights.sh "$EXP_ID"
    UPLOADED=1
else
    log "weights dataset 確認: $WEIGHTS_DATASET"
fi

# アップロード直後は Kaggle 側で processing 中。ready になるまで待たないと
# kernel push 時に "not valid dataset source" として attach されない。
if [ "$UPLOADED" = "1" ]; then
    log "weights dataset の処理完了(ready)を待機します..."
    WAITED=0
    while [ "$WAITED" -lt 600 ]; do
        if [ "$($KAGGLE datasets status "$WEIGHTS_DATASET" 2>/dev/null | tr -d '[:space:]')" = "ready" ]; then
            log "weights dataset ready。"
            break
        fi
        sleep 10
        WAITED=$((WAITED + 10))
    done
fi

# ── 3. kernel-metadata.json を用意して push ───────────────
KERNEL_SLUG="birdclef2026-$EXP_ID-sub"
KERNEL_ID="$USER_NAME/$KERNEL_SLUG"
KERNEL_URL="https://www.kaggle.com/code/$KERNEL_ID"
KERNEL_DIR="experiments/$EXP_ID/outputs/kernel"
mkdir -p "$KERNEL_DIR"
cp "$NOTEBOOK" "$KERNEL_DIR/$EXP_ID.ipynb"

# dataset_sources を [weights, extra...] の JSON 配列として組み立てる
DATASET_SOURCES_JSON="\"$WEIGHTS_DATASET\""
if [ -n "$EXTRA_DATASETS" ]; then
    IFS=',' read -ra _extras <<< "$EXTRA_DATASETS"
    for ds in "${_extras[@]}"; do
        ds="$(echo "$ds" | xargs)"  # trim
        [ -n "$ds" ] && DATASET_SOURCES_JSON="$DATASET_SOURCES_JSON, \"$ds\""
    done
fi

cat > "$KERNEL_DIR/kernel-metadata.json" <<EOF
{
  "id": "$KERNEL_ID",
  "title": "birdclef2026 $EXP_ID sub",
  "code_file": "$EXP_ID.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": $ENABLE_GPU,
  "enable_tpu": false,
  "enable_internet": false,
  "dataset_sources": [$DATASET_SOURCES_JSON],
  "competition_sources": ["$COMPETITION"],
  "kernel_sources": []
}
EOF

log "kernel を push します: $KERNEL_ID"
$KAGGLE kernels push -p "$KERNEL_DIR"

# ── 4. 記録（人間のレビュー待ち worklist） ───────────────
OOF_AUC="$(python -c "import json; d=json.load(open('$RESULTS_DIR/result.json')); print(d.get('metrics',{}).get('oof_macro_auc',''))" 2>/dev/null || echo "")"

LB="reports/leaderboard.md"
mkdir -p reports
if [ ! -f "$LB" ]; then
    cat > "$LB" <<'EOF'
# Leaderboard / 提出 worklist

`scripts/push_submission_notebook.sh` が Kaggle に Notebook を作成するたび1行追記する（status=PENDING_HUMAN_SUBMIT）。
人間が Kaggle 上で Notebook を確認 → Submit し、得られた Public/Private スコアをこの表に追記する。
plan-next / decide-submission は次サイクルでこの表を参照する。

| exp_id | OOF macro AUC | Public LB | Private LB | pushed_at (UTC) | kernel | status |
|--------|---------------|-----------|------------|-----------------|--------|--------|
EOF
fi
echo "| $EXP_ID | ${OOF_AUC:-} |  |  | ${TIMESTAMP} | $KERNEL_URL | PENDING_HUMAN_SUBMIT |" >> "$LB"

log "完了。Kaggle 上に Notebook を作成しました（提出はしていません）。"
log "  レビュー＆提出: $KERNEL_URL"
log "  worklist に記録: $LB"
