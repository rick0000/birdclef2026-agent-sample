"""Benchmark audio file loading speed."""
import time
from pathlib import Path

import numpy as np
import soundfile as sf

INPUT_ROOT = Path(__file__).resolve().parent.parent / "input"
SAMPLE_RATE = 32_000
N_FILES = 200

files = sorted(INPUT_ROOT.joinpath("train_audio").rglob("*.ogg"))[:N_FILES]
print(f"Benchmarking {len(files)} files\n")

# 1) Sequential soundfile.read
elapsed_list = []
for f in files:
    t0 = time.perf_counter()
    w, sr = sf.read(str(f), dtype="float32")
    elapsed_list.append(time.perf_counter() - t0)

total = sum(elapsed_list)
p50 = np.percentile(elapsed_list, 50) * 1000
p95 = np.percentile(elapsed_list, 95) * 1000
p99 = np.percentile(elapsed_list, 99) * 1000
print(f"soundfile sequential: {total:.2f}s total, {total/len(files)*1000:.1f}ms/file avg")
print(f"  p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms")

# 2) ProcessPoolExecutor (simulates actual pipeline)
from concurrent.futures import ProcessPoolExecutor, as_completed

def _load(path_str: str) -> tuple[str, int]:
    w, sr = sf.read(path_str, dtype="float32")
    return path_str, len(w)

for n_workers in [1, 2, 4, 8]:
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futs = [pool.submit(_load, str(f)) for f in files]
        for fut in futs:
            fut.result()
    elapsed = time.perf_counter() - t0
    print(f"ProcessPool workers={n_workers}: {elapsed:.2f}s total, {elapsed/len(files)*1000:.1f}ms/file")
