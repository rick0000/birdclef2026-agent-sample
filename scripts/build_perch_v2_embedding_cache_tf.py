"""Build a Perch v2 embedding cache using the TensorFlow Hub model.

Loads the Perch v2 SavedModel via ``tensorflow_hub``, processes every audio
file under ``input/`` into 5-second non-overlapping chunks, runs batched
GPU inference, and saves per-file ``(N_chunks, 1536)`` embedding arrays as
``.npy`` files under ``input/cache/perch_v2/``.

The output layout is identical to the ONNX-based
``build_perch_v2_embedding_cache.py`` so either script can populate the
cache interchangeably.

Usage:
    python scripts/build_perch_v2_embedding_cache_tf.py \\
        --batch-size 64 --num-workers 8
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from itertools import islice
from pathlib import Path

import numpy as np
import soundfile as sf

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import tensorflow as tf
import tensorflow_hub as hub
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_ROOT = PROJECT_ROOT / "input"
CACHE_ROOT = INPUT_ROOT / "cache" / "perch_v2"
TFHUB_CACHE = INPUT_ROOT / "cache" / "tfhub"

MODEL_URL = (
    "https://www.kaggle.com/models/"
    "google/bird-vocalization-classifier/tensorFlow2/perch_v2/2"
)

os.environ["TFHUB_CACHE_DIR"] = str(TFHUB_CACHE)

AUDIO_SUBDIRS = ("train_audio", "train_soundscapes", "test_soundscapes")
AUDIO_EXTS = {".ogg", ".wav", ".flac", ".mp3"}

SAMPLE_RATE = 32_000
CHUNK_SAMPLES = 160_000  # 5 s @ 32 kHz
EMBED_DIM = 1536

_SENTINEL = None  # signals end-of-stream to the consumer


# --------------------------------------------------------------------------- #
# Audio helpers
# --------------------------------------------------------------------------- #


def collect_audio_files() -> list[Path]:
    files: list[Path] = []
    for sub in AUDIO_SUBDIRS:
        root = INPUT_ROOT / sub
        if not root.exists():
            print(f"[warn] missing audio dir: {root}", file=sys.stderr)
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                files.append(p)
    return files


def cache_path_for(audio_path: Path) -> Path:
    rel = audio_path.relative_to(INPUT_ROOT)
    return (CACHE_ROOT / rel).with_suffix(".npy")


def chunkify(waveform: np.ndarray) -> np.ndarray:
    """Slice a 1-D waveform into ``(N, CHUNK_SAMPLES)`` with tail zero-pad."""
    if waveform.ndim != 1:
        waveform = waveform.reshape(-1)
    n = waveform.shape[0]
    if n == 0:
        return np.zeros((1, CHUNK_SAMPLES), dtype=np.float32)
    n_chunks = (n + CHUNK_SAMPLES - 1) // CHUNK_SAMPLES
    total = n_chunks * CHUNK_SAMPLES
    if total > n:
        waveform = np.pad(waveform, (0, total - n))
    return waveform.astype(np.float32, copy=False).reshape(n_chunks, CHUNK_SAMPLES)


def _load_and_chunkify(path_str: str) -> tuple[str, np.ndarray, str]:
    """Load a single audio file and return its chunks (runs in worker process)."""
    try:
        waveform, sr = sf.read(path_str, dtype="float32", always_2d=False)
        if waveform.ndim == 2:
            waveform = waveform.mean(axis=1)
        if sr != SAMPLE_RATE:
            import librosa

            waveform = librosa.resample(waveform, orig_sr=sr, target_sr=SAMPLE_RATE)
    except Exception as e:  # noqa: BLE001
        return path_str, np.zeros((0, CHUNK_SAMPLES), dtype=np.float32), repr(e)
    return path_str, chunkify(waveform), ""


def save_atomic(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, array)
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Number of 5-second chunks per inference call (default: 64).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-compute embeddings even if a cache file already exists.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many files (useful for smoke tests).",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=8,
        help="Number of worker processes decoding audio (default: 8).",
    )
    args = parser.parse_args()

    # ---- Load model --------------------------------------------------------
    print("[info] loading Perch v2 model from TensorFlow Hub ...", file=sys.stderr)
    model = hub.load(MODEL_URL)
    infer = model.signatures["serving_default"]
    print("[info] model loaded", file=sys.stderr)

    # Warmup with the exact batch_size to trigger XLA compilation once.
    _ = infer(inputs=tf.zeros((args.batch_size, CHUNK_SAMPLES), dtype=tf.float32))
    print("[info] warmup done", file=sys.stderr)

    # ---- Collect files -----------------------------------------------------
    files = collect_audio_files()
    print(f"[info] discovered {len(files)} audio files", file=sys.stderr)
    if args.limit is not None:
        files = files[: args.limit]
        print(f"[info] limited to first {len(files)} files", file=sys.stderr)

    n_skip = 0
    to_process: list[Path] = []
    for p in files:
        if cache_path_for(p).exists() and not args.overwrite:
            n_skip += 1
        else:
            to_process.append(p)
    print(
        f"[info] {len(to_process)} files to process ({n_skip} already cached)",
        file=sys.stderr,
    )
    if not to_process:
        print(f"[info] finished: done=0 skip={n_skip} fail=0", file=sys.stderr)
        return

    # ---- Chunk queue -------------------------------------------------------
    # Each item: (chunk_array (1, CHUNK_SAMPLES), file_path, chunk_index, total_chunks)
    # or _SENTINEL to signal end-of-stream.
    chunk_q: queue.Queue = queue.Queue(maxsize=args.batch_size * 4)

    # ---- Consumer thread: GPU inference + save -----------------------------
    stats = {"done": 0, "fail": 0}
    stats_lock = threading.Lock()

    def consumer() -> None:
        # Accumulate per-file embeddings as they arrive from batched inference.
        # file_embs[path] = (total_chunks, {chunk_idx: embedding})
        file_embs: dict[Path, tuple[int, dict[int, np.ndarray]]] = {}

        batch_chunks: list[np.ndarray] = []
        batch_meta: list[tuple[Path, int, int]] = []  # (path, chunk_idx, total)

        while True:
            item = chunk_q.get()
            if item is _SENTINEL:
                # Flush remaining
                if batch_chunks:
                    _run_batch(infer, batch_chunks, batch_meta, file_embs, stats,
                               stats_lock, args.batch_size)
                _save_completed(file_embs, stats, stats_lock)
                break

            chunk_arr, fpath, cidx, ctotal = item
            batch_chunks.append(chunk_arr)
            batch_meta.append((fpath, cidx, ctotal))

            if len(batch_chunks) == args.batch_size:
                _run_batch(infer, batch_chunks, batch_meta, file_embs, stats,
                           stats_lock, args.batch_size)
                batch_chunks = []
                batch_meta = []
                _save_completed(file_embs, stats, stats_lock)

    def _run_batch(
        infer_fn,
        chunks: list[np.ndarray],
        meta: list[tuple[Path, int, int]],
        file_embs: dict,
        stats: dict,
        lock: threading.Lock,
        batch_size: int,
    ) -> None:
        arr = np.concatenate(chunks, axis=0)  # (N, CHUNK_SAMPLES)
        try:
            inp = tf.constant(arr, dtype=tf.float32)
            out = infer_fn(inputs=inp)
            embs = out["embedding"].numpy()  # (N, EMBED_DIM)
        except Exception as e:  # noqa: BLE001
            print(f"[error] embed failed: {e}", file=sys.stderr)
            with lock:
                stats["fail"] += len(meta)
            return

        for i, (fpath, cidx, ctotal) in enumerate(meta):
            if fpath not in file_embs:
                file_embs[fpath] = (ctotal, {})
            file_embs[fpath][1][cidx] = embs[i]

    def _save_completed(
        file_embs: dict[Path, tuple[int, dict[int, np.ndarray]]],
        stats: dict,
        lock: threading.Lock,
    ) -> None:
        done_keys = [
            p for p, (total, parts) in file_embs.items() if len(parts) == total
        ]
        for p in done_keys:
            total, parts = file_embs.pop(p)
            stacked = np.stack([parts[i] for i in range(total)], axis=0)
            try:
                save_atomic(cache_path_for(p), stacked)
                with lock:
                    stats["done"] += 1
            except Exception as e:  # noqa: BLE001
                print(f"[error] save failed: {p}: {e}", file=sys.stderr)
                with lock:
                    stats["fail"] += 1

    consumer_thread = threading.Thread(target=consumer, daemon=True)
    consumer_thread.start()

    # ---- Producer: load audio + enqueue chunks -----------------------------
    n_fail_load = 0
    pbar = tqdm(
        total=len(to_process), desc="perch_v2_tf", unit="file", dynamic_ncols=True
    )

    prefetch = args.num_workers * 3
    pool = ProcessPoolExecutor(max_workers=args.num_workers)
    path_iter = iter(to_process)
    pending: deque = deque()
    for p in islice(path_iter, prefetch):
        pending.append(pool.submit(_load_and_chunkify, str(p)))

    try:
        while pending:
            fut = pending.popleft()
            path_str, chunks, err = fut.result()
            pbar.update(1)

            nxt = next(path_iter, None)
            if nxt is not None:
                pending.append(pool.submit(_load_and_chunkify, str(nxt)))

            if err:
                print(f"[error] load failed: {path_str}: {err}", file=sys.stderr)
                n_fail_load += 1
                with stats_lock:
                    pbar.set_postfix(
                        done=stats["done"], fail=stats["fail"] + n_fail_load, skip=n_skip
                    )
                continue

            fpath = Path(path_str)
            n_chunks = int(chunks.shape[0])
            for ci in range(n_chunks):
                chunk_q.put((chunks[ci : ci + 1], fpath, ci, n_chunks))

            with stats_lock:
                pbar.set_postfix(
                    done=stats["done"], fail=stats["fail"] + n_fail_load, skip=n_skip
                )

        # Signal consumer to finish and wait
        chunk_q.put(_SENTINEL)
        consumer_thread.join()

    except KeyboardInterrupt:
        print("\n[info] interrupted, shutting down ...", file=sys.stderr)

    pool.shutdown(wait=False, cancel_futures=True)

    pbar.set_postfix(
        done=stats["done"], fail=stats["fail"] + n_fail_load, skip=n_skip
    )
    pbar.close()

    total_fail = stats["fail"] + n_fail_load
    print(
        f"[info] finished: done={stats['done']} skip={n_skip} fail={total_fail}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
