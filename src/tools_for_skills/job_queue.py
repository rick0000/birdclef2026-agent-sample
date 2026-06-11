"""job_queue -- 実験ジョブの状態管理

状態遷移:
    not_executed → executing → done → report_done
                       ↓
                    failed

ディレクトリ構造:
    job_queue/{not_executed,executing,done,report_done,failed}/<experiment_id>.json

Usage:
    python -m src.tools_for_skills.job_queue enqueue <experiment_id> --config-path <path> [--depends-on <id>]
    python -m src.tools_for_skills.job_queue list [--state <state>]
    python -m src.tools_for_skills.job_queue count [--state <state>]
    python -m src.tools_for_skills.job_queue transition <experiment_id> <target_state>
    python -m src.tools_for_skills.job_queue pick-next
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUEUE_DIR = PROJECT_ROOT / "job_queue"


class State(str, Enum):
    NOT_EXECUTED = "not_executed"
    EXECUTING = "executing"
    DONE = "done"
    REPORTED = "reported"
    KNOWLEDGE_UPDATED = "knowledge_updated"
    COMPLETED = "completed"
    FAILED = "failed"


VALID_TRANSITIONS: dict[State, list[State]] = {
    State.NOT_EXECUTED: [State.EXECUTING],
    State.EXECUTING: [State.DONE, State.FAILED],
    State.DONE: [State.REPORTED],
    State.REPORTED: [State.KNOWLEDGE_UPDATED],
    State.KNOWLEDGE_UPDATED: [State.COMPLETED],
    State.COMPLETED: [],
    State.FAILED: [State.NOT_EXECUTED],  # リトライ可能
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    experiment_id: str
    config_path: str
    depends_on: Optional[str] = None
    status: State = State.NOT_EXECUTED
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Job:
        known = {f.name for f in __import__("dataclasses").fields(cls)}
        d = {k: v for k, v in d.items() if k in known}
        d["status"] = State(d["status"])
        return cls(**d)

    @classmethod
    def from_file(cls, path: Path) -> Job:
        return cls.from_dict(json.loads(path.read_text()))


class JobQueue:
    """ファイルシステムベースのジョブキュー。"""

    def __init__(self, base_dir: Path = QUEUE_DIR):
        self.base_dir = base_dir
        for state in State:
            (self.base_dir / state.value).mkdir(parents=True, exist_ok=True)

    def _dir(self, state: State) -> Path:
        return self.base_dir / state.value

    def _path(self, experiment_id: str, state: State) -> Path:
        return self._dir(state) / f"{experiment_id}.json"

    def _save(self, job: Job) -> Path:
        path = self._path(job.experiment_id, job.status)
        path.write_text(json.dumps(job.to_dict(), indent=2, ensure_ascii=False))
        return path

    def find(self, experiment_id: str) -> tuple[Optional[Job], Optional[State]]:
        """全状態から experiment_id を探す。"""
        for state in State:
            path = self._path(experiment_id, state)
            if path.exists():
                return Job.from_file(path), state
        return None, None

    # ── Public API ──

    def enqueue(
        self,
        experiment_id: str,
        config_path: str,
        depends_on: Optional[str] = None,
    ) -> Job:
        """ジョブを not_executed に作成する。既存なら例外。"""
        existing, existing_state = self.find(experiment_id)
        if existing is not None:
            raise ValueError(
                f"{experiment_id} は既に {existing_state.value}/ に存在します"
            )
        job = Job(
            experiment_id=experiment_id,
            config_path=config_path,
            depends_on=depends_on,
        )
        self._save(job)
        return job

    def transition(
        self,
        experiment_id: str,
        target: State,
        error_message: Optional[str] = None,
    ) -> Job:
        """ジョブを別の状態へ遷移させる。"""
        job, current = self.find(experiment_id)
        if job is None:
            raise FileNotFoundError(f"{experiment_id} が見つかりません")

        if target not in VALID_TRANSITIONS[current]:
            raise ValueError(
                f"{current.value} → {target.value} は無効な遷移です "
                f"(許可: {[s.value for s in VALID_TRANSITIONS[current]]})"
            )

        src = self._path(experiment_id, current)

        if target == State.EXECUTING:
            job.started_at = _now_iso()
        elif target in (State.DONE, State.FAILED):
            job.finished_at = _now_iso()
        if error_message:
            job.error_message = error_message

        job.status = target
        dst = self._path(experiment_id, target)
        dst.write_text(json.dumps(job.to_dict(), indent=2, ensure_ascii=False))
        src.unlink()
        return job

    def list_jobs(self, state: Optional[State] = None) -> list[Job]:
        """ジョブ一覧を返す。state 指定で絞り込み。"""
        states = [state] if state else list(State)
        jobs: list[Job] = []
        for s in states:
            for path in sorted(self._dir(s).glob("*.json")):
                jobs.append(Job.from_file(path))
        return jobs

    def count(self, state: Optional[State] = None) -> int:
        """ジョブ数を返す。"""
        return len(self.list_jobs(state))

    def pick_next(self) -> Optional[Job]:
        """not_executed から次に実行可能なジョブを返す。

        depends_on がある場合、依存先が completed でなければスキップ。
        """
        for job in self.list_jobs(State.NOT_EXECUTED):
            if job.depends_on:
                _, dep_state = self.find(job.depends_on)
                if dep_state != State.COMPLETED:
                    continue
            return job
        return None

    def pending_count(self) -> int:
        """not_executed + executing のジョブ数。Agent1 の投入判断に使う。"""
        return self.count(State.NOT_EXECUTED) + self.count(State.EXECUTING)


# ── CLI ──────────────────────────────────────────────────────


def cmd_enqueue(args: argparse.Namespace) -> None:
    q = JobQueue()
    try:
        job = q.enqueue(args.experiment_id, args.config_path, args.depends_on)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {job.experiment_id} → not_executed/")


def cmd_list(args: argparse.Namespace) -> None:
    q = JobQueue()
    state = State(args.state) if args.state else None
    jobs = q.list_jobs(state)
    if not jobs:
        print("ジョブなし")
        return
    for job in jobs:
        dep = f"  (depends_on: {job.depends_on})" if job.depends_on else ""
        print(f"[{job.status.value}] {job.experiment_id}  {job.config_path}{dep}")


def cmd_count(args: argparse.Namespace) -> None:
    q = JobQueue()
    if args.state:
        print(f"{args.state}: {q.count(State(args.state))}")
    else:
        jobs = q.list_jobs()
        counts = Counter(j.status.value for j in jobs)
        for s in State:
            if counts[s.value]:
                print(f"{s.value}: {counts[s.value]}")
        print(f"total: {len(jobs)}")


def cmd_transition(args: argparse.Namespace) -> None:
    q = JobQueue()
    try:
        job = q.transition(args.experiment_id, State(args.target_state))
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {job.experiment_id} → {args.target_state}/")


def cmd_pick_next(args: argparse.Namespace) -> None:
    q = JobQueue()
    job = q.pick_next()
    if job is None:
        print("実行可能なジョブなし")
    else:
        print(job.experiment_id)


def build_parser() -> argparse.ArgumentParser:
    state_names = [s.value for s in State]
    parser = argparse.ArgumentParser(description="実験ジョブキュー管理")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("enqueue")
    p.add_argument("experiment_id")
    p.add_argument("--config-path", required=True)
    p.add_argument("--depends-on", default=None)

    p = sub.add_parser("list")
    p.add_argument("--state", choices=state_names, default=None)

    p = sub.add_parser("count")
    p.add_argument("--state", choices=state_names, default=None)

    p = sub.add_parser("transition")
    p.add_argument("experiment_id")
    p.add_argument("target_state", choices=state_names)

    sub.add_parser("pick-next")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "enqueue": cmd_enqueue,
        "list": cmd_list,
        "count": cmd_count,
        "transition": cmd_transition,
        "pick-next": cmd_pick_next,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
