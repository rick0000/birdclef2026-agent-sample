"""Baseline: Perch v2 cached embeddings (train_audio) + Linear head (PyTorch).

Pipeline:
  1. Load pre-computed perch v2 embeddings from cache (mean pool per clip)
  2. Load train.csv labels (single-label per clip)
  3. OOF evaluation with StratifiedKFold (linear classifier)
  4. Evaluate macro ROC-AUC
  5. Save results + analysis files
"""

import json
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader, TensorDataset

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EXP_ID = "exp0000"
DEBUG = os.environ.get("DEBUG", "0") == "1"
DEBUG_SAMPLES_PER_CLASS = 10

INPUT_DIR = Path("input")
CACHE_DIR = INPUT_DIR / "cache" / "perch_v2" / "train_audio"
RESULTS_DIR = Path("experiments") / EXP_ID / "outputs" / "results"
CKPT_DIR = Path("experiments") / EXP_ID / "outputs" / "checkpoints"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR.mkdir(parents=True, exist_ok=True)

N_SPLITS = 5
LR = 1e-3
EPOCHS = 50 if not DEBUG else 5
BATCH_SIZE = 256
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

t0 = time.time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def macro_auc_skip_empty(y_true, y_score):
    keep = y_true.sum(axis=0) > 0
    if keep.sum() == 0:
        return 0.0
    return float(roc_auc_score(y_true[:, keep], y_score[:, keep], average="macro"))


# ===========================================================================
# STEP 1: Load data & labels
# ===========================================================================
print(f"[{EXP_ID}] Loading data... (DEBUG={DEBUG})")
train = pd.read_csv(INPUT_DIR / "train.csv")
sample_sub = pd.read_csv(INPUT_DIR / "sample_submission.csv", nrows=1)

PRIMARY_LABELS = sample_sub.columns[1:].tolist()
N_CLASSES = len(PRIMARY_LABELS)
label_to_idx = {c: i for i, c in enumerate(PRIMARY_LABELS)}

train["primary_label"] = train["primary_label"].astype(str)

if DEBUG:
    idx = (
        train.groupby("primary_label")
        .apply(lambda g: g.sample(min(len(g), DEBUG_SAMPLES_PER_CLASS), random_state=42).index.tolist())
    )
    train = train.loc[[i for ids in idx for i in ids]].reset_index(drop=True)

print(f"  train.csv: {train.shape[0]} clips, {train['primary_label'].nunique()} classes")

# ===========================================================================
# STEP 2: Load cached embeddings (mean pool per clip)
# ===========================================================================
print(f"[{EXP_ID}] Loading cached embeddings...")

emb_list = []
label_list = []
filename_list = []

for _, row in train.iterrows():
    cache_path = CACHE_DIR / row["filename"].replace(".ogg", ".npy")
    if not cache_path.exists():
        continue
    label = str(row["primary_label"])
    if label not in label_to_idx:
        continue

    emb = np.load(cache_path)  # (n_chunks, 1536)
    emb_list.append(emb.mean(axis=0))
    label_list.append(label)
    filename_list.append(row["filename"])

X = np.stack(emb_list, axis=0).astype(np.float32)  # (N, 1536)
y_single = np.array([label_to_idx[l] for l in label_list], dtype=np.int64)

# Multi-hot for AUC evaluation
Y = np.zeros((len(label_list), N_CLASSES), dtype=np.uint8)
for i, idx in enumerate(y_single):
    Y[i, idx] = 1

print(f"  Embeddings: {X.shape}")
print(f"  Active classes: {len(set(label_list))}")
print(f"  Device: {DEVICE}")

# ===========================================================================
# STEP 3: OOF evaluation with StratifiedKFold
# ===========================================================================
print(f"[{EXP_ID}] Running OOF evaluation ({N_SPLITS}-fold, {EPOCHS} epochs)...")

skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
oof_scores = np.zeros((len(X), N_CLASSES), dtype=np.float32)
fold_ids = np.full(len(X), -1, dtype=np.int16)

for fold, (tr_idx, va_idx) in enumerate(skf.split(X, y_single), 1):
    fold_ids[va_idx] = fold

    X_tr = torch.tensor(X[tr_idx], device=DEVICE)
    y_tr = torch.tensor(y_single[tr_idx], device=DEVICE)
    X_va = torch.tensor(X[va_idx], device=DEVICE)

    train_ds = TensorDataset(X_tr, y_tr)
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)

    model = nn.Linear(X.shape[1], N_CLASSES).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(EPOCHS):
        epoch_loss = 0.0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(xb)
        epoch_loss /= len(tr_idx)

    model.eval()
    with torch.no_grad():
        logits = model(X_va)
        probs = torch.softmax(logits, dim=1).cpu().numpy()
    oof_scores[va_idx] = probs

    va_auc = macro_auc_skip_empty(Y[va_idx], probs)
    print(f"  Fold {fold}: {len(va_idx)} val clips, loss={epoch_loss:.4f}, AUC={va_auc:.4f}")

# ===========================================================================
# STEP 4: Evaluate
# ===========================================================================
oof_auc = macro_auc_skip_empty(Y, oof_scores)
print(f"\n  OOF macro AUC: {oof_auc:.6f}")

# ===========================================================================
# STEP 4.5: Save analysis files
# ===========================================================================
print(f"[{EXP_ID}] Saving analysis files...")

oof_pred_df = pd.DataFrame(oof_scores, columns=PRIMARY_LABELS)
oof_pred_df.insert(0, "filename", filename_list)
oof_pred_df.insert(1, "true_label", label_list)
oof_pred_df.insert(2, "fold", fold_ids)
oof_pred_df.to_csv(RESULTS_DIR / "oof_predictions.csv", index=False)

oof_gt_df = pd.DataFrame(Y, columns=PRIMARY_LABELS)
oof_gt_df.insert(0, "filename", filename_list)
oof_gt_df.insert(1, "true_label", label_list)
oof_gt_df.insert(2, "fold", fold_ids)
oof_gt_df.to_csv(RESULTS_DIR / "oof_ground_truth.csv", index=False)

per_class = []
for cls_idx, label in enumerate(PRIMARY_LABELS):
    n_pos = int(Y[:, cls_idx].sum())
    cls_auc = float("nan")
    if n_pos > 0 and n_pos < len(Y):
        try:
            cls_auc = float(roc_auc_score(Y[:, cls_idx], oof_scores[:, cls_idx]))
        except ValueError:
            pass
    per_class.append({
        "label": label,
        "n_positive": n_pos,
        "auc": cls_auc,
    })
per_class_df = pd.DataFrame(per_class).sort_values("auc", ascending=True)
per_class_df.to_csv(RESULTS_DIR / "per_class_metrics.csv", index=False)

print(f"  oof_predictions.csv: {oof_pred_df.shape}")
print(f"  oof_ground_truth.csv: {oof_gt_df.shape}")
print(f"  per_class_metrics.csv: {per_class_df.shape}")

# ===========================================================================
# STEP 4.6: Fit final model on full data and save checkpoint (for submission)
# ===========================================================================
print(f"[{EXP_ID}] Fitting final model on full data for submission...")

X_full = torch.tensor(X, device=DEVICE)
y_full = torch.tensor(y_single, device=DEVICE)
full_ds = TensorDataset(X_full, y_full)
full_dl = DataLoader(full_ds, batch_size=BATCH_SIZE, shuffle=True)

final_model = nn.Linear(X.shape[1], N_CLASSES).to(DEVICE)
optimizer = torch.optim.Adam(final_model.parameters(), lr=LR)
criterion = nn.CrossEntropyLoss()

final_model.train()
for epoch in range(EPOCHS):
    for xb, yb in full_dl:
        optimizer.zero_grad()
        criterion(final_model(xb), yb).backward()
        optimizer.step()

torch.save(final_model.state_dict(), CKPT_DIR / "model.pt")
with open(CKPT_DIR / "meta.json", "w") as f:
    json.dump(
        {
            "experiment_id": EXP_ID,
            "primary_labels": PRIMARY_LABELS,
            "embedding_dim": int(X.shape[1]),
            "n_classes": int(N_CLASSES),
            "model_arch": "nn.Linear",
            "input_pooling": "mean",
            "embedding_model": "perch_v2",
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
print(f"  Saved checkpoint: {CKPT_DIR / 'model.pt'}")
print(f"  Saved meta:       {CKPT_DIR / 'meta.json'}")

elapsed = time.time() - t0
print(f"\n[{EXP_ID}] Done in {elapsed:.1f}s")

# ===========================================================================
# STEP 5: Save results
# ===========================================================================
results = {
    "experiment_id": EXP_ID,
    "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
    "metrics": {
        "loss": 0.0,
        "score": float(oof_auc),
        "oof_macro_auc": float(oof_auc),
    },
    "config_summary": {
        "method": "perch_v2_embedding (mean pool) + nn.Linear",
        "data": "train_audio",
        "embedding_dim": 1536,
        "lr": LR,
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "n_splits": N_SPLITS,
        "n_clips": len(X),
        "n_classes": N_CLASSES,
        "n_active_classes": len(set(label_list)),
        "device": DEVICE,
        "debug": DEBUG,
    },
    "elapsed_seconds": elapsed,
}

results_path = RESULTS_DIR / "result.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Saved results to {results_path}")
