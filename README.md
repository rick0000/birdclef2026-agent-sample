# BirdCLEF2026 × Claude Code Starter
Claude Code で[BirdCLEF2026](https://www.kaggle.com/competitions/birdclef-2026) コンペティションを解く試みです。

## 使い方
- データのダウンロード & 展開
```
export KAGGLE_API_TOKEN=<Your token>
bash scripts/prepare.sh
# Docker イメージをビルドしてコンテナを起動
bash scripts/run_docker_claude.sh
```
コンテナに入ったら `claude` で Claude Code を起動してください。

## ハーネスの運用
2層実行モデル（Bash層で実験を回し、Claude層の各スキルが状態遷移を担当）で自律的に実験を進めます。本番構成（bash runner + `/loop` スキル群）はまとめて起動できます。

```
bash scripts/run_full_harness.sh      # tmux に runner + 監視 /loop を一括起動
tmux attach -t birdclef               # 様子を見る
bash scripts/stop_full_harness.sh     # 停止
```

アーキテクチャ・状態遷移・スキル・提出フローの詳細は [CLAUDE.md](CLAUDE.md) を参照してください。
