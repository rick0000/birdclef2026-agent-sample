"""kaggle_submit -- Kaggle 提出枠の確認とスコア取得

Kaggle Notebook の作成(kernel push)は scripts/push_submission_notebook.sh が担当し、
実際の Submit は人間が Kaggle 上で手動で行う。このモジュールは

  - budget: 当日の提出回数と残枠を表示（decide-submission の判断材料）
  - latest: 最新提出の状態とスコアを返す（提出後のスコア反映ポーリングに利用）

という「Kaggle submissions CSV のパース」だけを担う薄いラッパ。
日付・スコアのパースが bash より素直に書けるので Python に切り出している。

Usage:
    python -m src.tools_for_skills.kaggle_submit budget [--limit N]
    python -m src.tools_for_skills.kaggle_submit latest [--field <name>] [--since <iso>]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


COMPETITION = "birdclef-2026"
DEFAULT_DAILY_LIMIT = 100  # コンペ終了後の late submission は 100 回/日。env KAGGLE_DAILY_LIMIT で上書き可。


@dataclass
class Submission:
    file_name: str
    date: Optional[datetime]
    description: str
    status: str
    public_score: Optional[float]
    private_score: Optional[float]


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if not raw:
        return None
    # 例: "2026-03-20 02:08:01.917000" (UTC)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_score(raw: str) -> Optional[float]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def fetch_submissions() -> list[Submission]:
    """`kaggle competitions submissions <comp> --csv` をパースして新しい順で返す。"""
    # kaggle CLI は v2.2+ を uv 経由で（PATH の bare kaggle は旧 1.7.x のことがある）。
    # KAGGLE_CMD で上書き可（例: "kaggle"）。
    import os
    import shlex

    cmd = shlex.split(os.environ.get("KAGGLE_CMD", "uv run kaggle"))
    proc = subprocess.run(
        [*cmd, "competitions", "submissions", COMPETITION, "--csv"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kaggle submissions の取得に失敗しました: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    reader = csv.DictReader(io.StringIO(proc.stdout))
    subs: list[Submission] = []
    for row in reader:
        subs.append(
            Submission(
                file_name=row.get("fileName", "").strip(),
                date=_parse_date(row.get("date", "")),
                description=row.get("description", "").strip(),
                # "SubmissionStatus.COMPLETE" → "COMPLETE"
                status=row.get("status", "").strip().split(".")[-1],
                public_score=_parse_score(row.get("publicScore", "")),
                private_score=_parse_score(row.get("privateScore", "")),
            )
        )
    # date 降順（None は末尾）
    subs.sort(key=lambda s: (s.date is not None, s.date or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return subs


# ── CLI ──────────────────────────────────────────────────────


def cmd_budget(args: argparse.Namespace) -> None:
    import os

    limit = args.limit or int(os.environ.get("KAGGLE_DAILY_LIMIT", DEFAULT_DAILY_LIMIT))
    today = datetime.now(timezone.utc).date()

    try:
        subs = fetch_submissions()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    used = sum(1 for s in subs if s.date is not None and s.date.date() == today)
    remaining = max(0, limit - used)
    print(f"used={used} limit={limit} remaining={remaining} date={today.isoformat()}")


def cmd_latest(args: argparse.Namespace) -> None:
    try:
        subs = fetch_submissions()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.since:
        try:
            since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        except ValueError:
            since = _parse_date(args.since.replace("T", " "))
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        subs = [s for s in subs if s.date is not None and (since is None or s.date > since)]

    if not subs:
        if args.field:
            print("")  # フィールド指定時は空文字で「該当なし」を表す
        else:
            print(json.dumps({"found": False}))
        return

    latest = subs[0]
    payload = {
        "found": True,
        "file_name": latest.file_name,
        "date": latest.date.isoformat() if latest.date else None,
        "description": latest.description,
        "status": latest.status,
        "public_score": latest.public_score,
        "private_score": latest.private_score,
    }
    if args.field:
        value = payload.get(args.field, "")
        print("" if value is None else value)
    else:
        print(json.dumps(payload, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kaggle 提出枠・スコア取得")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("budget", help="当日の提出回数と残枠を表示")
    p.add_argument("--limit", type=int, default=None, help="1日の提出上限（既定: env KAGGLE_DAILY_LIMIT または 5）")

    p = sub.add_parser("latest", help="最新提出の状態・スコアを表示")
    p.add_argument("--field", default=None, help="単一フィールドのみ出力 (date/status/public_score など)")
    p.add_argument("--since", default=None, help="このISO時刻より新しい提出だけを対象にする")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "budget": cmd_budget,
        "latest": cmd_latest,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
