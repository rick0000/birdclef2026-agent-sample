#!/bin/bash
# reset_outputs.sh — エージェント生成物をすべて削除する
#
# 削除対象:
#   - experiments/exp* (exp0000 以外のディレクトリ全体)
#   - experiments/exp0000/outputs/ (新レイアウト) と results/, logs/ (旧レイアウト)
#   - reports/ 配下の .md / .html
#   - knowledge/experiments/ 配下の .md
#   - knowledge/strategy.md
#   - docs/whole_report.html
#   - job_queue/ 配下の .json (.gitkeep は残す)
#
# 残るもの:
#   - experiments/exp0000/ のコード本体 (config.json, train.py, run.sh)
#   - experiments/baseline/ (テンプレ用、未使用なら手動削除)
#   - knowledge/resources/ (外部リソース知見、手動管理)
#   - submissions/ (提出履歴は別管理)
#
# このスクリプトは job_queue を空にするだけで enqueue はしない。
# 再開時は別途:
#   python -m src.tools_for_skills.job_queue enqueue exp0000 --config-path experiments/exp0000/config.json

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[reset] removing generated experiments..."
for d in experiments/exp*; do
    [ "$d" = "experiments/exp0000" ] && continue
    [ -d "$d" ] && rm -rf "$d"
done

echo "[reset] removing exp0000 outputs..."
rm -rf experiments/exp0000/outputs experiments/exp0000/results experiments/exp0000/logs

echo "[reset] removing reports/ and knowledge/ outputs..."
rm -f reports/*.md reports/*.html
rm -f knowledge/experiments/*.md
rm -f knowledge/strategy.md
rm -f docs/whole_report.html

echo "[reset] clearing job_queue (preserve .gitkeep)..."
find job_queue -type f ! -name '.gitkeep' -delete

echo "[reset] enqueueing exp0000..."
python -m src.tools_for_skills.job_queue enqueue exp0000 --config-path experiments/exp0000/config.json

echo "[reset] done."
