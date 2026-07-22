
import os
import random
import itertools
import pickle
import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import optuna
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_curve,
    auc,
    balanced_accuracy_score
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from xgboost import XGBClassifier


MODELS_TO_USE = ["VGG-Face", "Facenet", "Facenet512", "ArcFace"]
EMBEDDING_CACHE_FILE = "all_model_embeddings_4_models.pkl"
MAX_PAIRS_PER_TYPE = 2000
FACES_DIR = "faces"
DISTANCE_METRIC = "cosine"
RANDOM_STATE = 42
MODEL_FILE = "best_face_verification_model.pkl"
OPTUNA_TRIALS = 25  # increase if you want a larger search


def load_embedding_maps(path):
    if not os.path.exists(path):
        raise SystemExit(f"Error: Embedding cache file not found at '{path}'.")
    with open(path, "rb") as f:
        return pickle.load(f)

def normalize_key_variants(path):
    variants = []
    p = path.replace("\\", "/")
    variants.append(p)
    variants.append(os.path.basename(p))
    variants.append(p.lower())
    variants.append(os.path.basename(p).lower())
    return variants

def extract_numbers_recursive(x, out):
    if isinstance(x, dict):
        if "embedding" in x and isinstance(x["embedding"], (list, tuple, np.ndarray)):
            extract_numbers_recursive(x["embedding"], out)
        else:
            for v in x.values():
                extract_numbers_recursive(v, out)
    elif isinstance(x, (list, tuple, np.ndarray)):
        for v in x:
            extract_numbers_recursive(v, out)
    elif isinstance(x, (int, float, np.number)):
        out.append(float(x))

def flatten_emb(e):
    """
    Safely flatten possible embedding representations into 1D numpy array.
    Accepts: raw list/ndarray, dict containing 'embedding', nested dict/list structures.
    """
    numbers = []
    extract_numbers_recursive(e, numbers)
    return np.array(numbers, dtype=np.float32)

def get_embedding_for_image(emb_map, img_path):
    """
    Try multiple key lookups to find embedding for an image path.
    Returns raw stored embedding object (may be list, ndarray, dict) or None.
    """
    if emb_map is None:
        return None
    # exact path keys
    if img_path in emb_map:
        val = emb_map[img_path]
        return val.get("embedding") if isinstance(val, dict) and "embedding" in val else val
    # basename keys
    base = os.path.basename(img_path)
    if base in emb_map:
        val = emb_map[base]
        return val.get("embedding") if isinstance(val, dict) and "embedding" in val else val
    # normalized forms
    for v in normalize_key_variants(img_path):
        if v in emb_map:
            val = emb_map[v]
            return val.get("embedding") if isinstance(val, dict) and "embedding" in val else val
    # try case-insensitive basename matching
    base_lower = base.lower()
    for k in list(emb_map.keys()):
        if isinstance(k, str) and os.path.basename(k).lower() == base_lower:
            val = emb_map[k]
            return val.get("embedding") if isinstance(val, dict) and "embedding" in val else val
    return None

def create_pairs_from_dir(faces_dir, max_genuine, max_impostor):
    """
    constructs genuine and impostor pairs from directory structure:
    faces/<person>/<images...>
    """
    person_to_images = {}
    all_people = []
    for person_name in sorted(os.listdir(faces_dir)):
        person_path = os.path.join(faces_dir, person_name)
        if not os.path.isdir(person_path):
            continue
        images = [
            os.path.join(person_path, f).replace("\\", "/")
            for f in sorted(os.listdir(person_path))
            if f.lower().endswith((".jpg", ".png", ".jpeg"))
        ]
        if len(images) >= 2:
            person_to_images[person_name] = images
            all_people.append(person_name)

    genuine_pairs = []
    for person, imgs in person_to_images.items():
        genuine_pairs.extend(itertools.combinations(imgs, 2))
    if len(genuine_pairs) > max_genuine:
        genuine_pairs = random.sample(genuine_pairs, max_genuine)

    impostor_pairs = []
    # sample unique impostor pairs
    while len(impostor_pairs) < max_impostor and len(all_people) >= 2:
        try:
            p1, p2 = random.sample(all_people, 2)
            img1 = random.choice(person_to_images[p1])
            img2 = random.choice(person_to_images[p2])
            if (img1, img2) not in impostor_pairs and (img2, img1) not in impostor_pairs:
                impostor_pairs.append((img1, img2))
        except Exception:
            continue
    return genuine_pairs, impostor_pairs

def auto_sweep_thresholds(embedding_maps, faces_dir):
    """
    Compute a per-backbone threshold guess using sample same/different pairs.
    This is a lightweight heuristic and is clamped to [0.3, 0.95].
    """
    thresholds = {}
    people = [p for p in os.listdir(faces_dir) if os.path.isdir(os.path.join(faces_dir, p))]
    for model in MODELS_TO_USE:
        scores = []
        # try to gather a few sample same/different scores
        if len(people) < 2:
            thresholds[model] = 0.5
            continue
        # iterate some persons until we collect a few samples
        for p in random.sample(people, min(len(people), 6)):
            imgs = [os.path.join(faces_dir, p, f) for f in os.listdir(os.path.join(faces_dir, p))]
            if len(imgs) < 2:
                continue
            # same
            a, b = imgs[0], imgs[1]
            e1 = get_embedding_for_image(embedding_maps.get(model, {}), a)
            e2 = get_embedding_for_image(embedding_maps.get(model, {}), b)
            if e1 is None or e2 is None:
                continue
            e1, e2 = flatten_emb(e1), flatten_emb(e2)
            min_len = min(e1.size, e2.size)
            if min_len == 0:
                continue
            e1, e2 = e1[:min_len], e2[:min_len]
            cosine = float(np.dot(e1, e2) / ((np.linalg.norm(e1) * np.linalg.norm(e2)) + 1e-10))
            scores.append(cosine)
            # different (pick another person)
            others = [q for q in people if q != p]
            if not others:
                continue
            q = random.choice(others)
            imgs_q = [os.path.join(faces_dir, q, f) for f in os.listdir(os.path.join(faces_dir, q))]
            if not imgs_q:
                continue
            c = imgs_q[0]
            e3 = get_embedding_for_image(embedding_maps.get(model, {}), c)
            if e3 is None:
                continue
            e3 = flatten_emb(e3)
            min_len2 = min(e1.size, e3.size)
            if min_len2 == 0:
                continue
            cosine_diff = float(np.dot(e1[:min_len2], e3[:min_len2]) / ((np.linalg.norm(e1[:min_len2]) * np.linalg.norm(e3[:min_len2])) + 1e-10))
            scores.append(cosine_diff)
        if scores:
            median = float(np.median(scores))
            thresholds[model] = float(np.clip(median, 0.3, 0.95))
        else:
            thresholds[model] = 0.5
    return thresholds

def compute_pair_features(pairs, embedding_maps, thresholds):
    """
    For each pair compute [dist, norm_score] per backbone, yielding 2 * len(MODELS_TO_USE) features.
    Skips pairs missing embeddings.
    """
    X, y, meta = [], [], []
    for name1, name2, label in tqdm(pairs, desc="pairs"):
        feats = []
        skip_pair = False
        for model_name in MODELS_TO_USE:
            emb_map = embedding_maps.get(model_name, {})
            e1_raw = get_embedding_for_image(emb_map, name1)
            e2_raw = get_embedding_for_image(emb_map, name2)
            if e1_raw is None or e2_raw is None:
                skip_pair = True
                break
            e1 = flatten_emb(e1_raw)
            e2 = flatten_emb(e2_raw)
            if e1.size == 0 or e2.size == 0:
                skip_pair = True
                break
            min_len = min(e1.size, e2.size)
            e1, e2 = e1[:min_len], e2[:min_len]
            cosine = float(np.dot(e1, e2) / ((np.linalg.norm(e1) * np.linalg.norm(e2)) + 1e-10))
            dist = 1.0 - cosine
            thresh = thresholds.get(model_name, 0.5)
            norm_score = max(0.0, 1.0 - (dist / (thresh + 1e-10)))
            feats.extend([float(dist), float(norm_score)])
        if not skip_pair:
            X.append(feats)
            y.append(int(label))
            meta.append((name1, name2))
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32), meta

def prepare_dataset(genuine_pairs, impostor_pairs, embedding_maps, thresholds):
    pairs = [(a, b, 1) for a, b in genuine_pairs] + [(a, b, 0) for a, b in impostor_pairs]
    random.shuffle(pairs)
    X, y, meta = compute_pair_features(pairs, embedding_maps, thresholds)
    if X.size == 0:
        raise SystemExit("Error: No valid pairs after filtering missing embeddings.")
    return X, y, meta



def build_clf_from_trial(trial):
    """
    Create a new classifier instance based on trial suggestion (for use in objective).
    """
    model_type = trial.suggest_categorical("model", ["logreg", "rf", "svm", "xgb"])
    if model_type == "logreg":
        C = trial.suggest_float("C", 0.01, 10, log=True)
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=C, solver="liblinear", class_weight="balanced", random_state=RANDOM_STATE))
        ])
    elif model_type == "rf":
        clf = RandomForestClassifier(
            n_estimators=trial.suggest_int("n_estimators", 50, 300),
            max_depth=trial.suggest_int("max_depth", 3, 15),
            random_state=RANDOM_STATE,
            class_weight="balanced"
        )
    elif model_type == "svm":
        C = trial.suggest_float("C", 0.1, 10, log=True)
        gamma = trial.suggest_float("gamma", 1e-4, 1, log=True)
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(C=C, gamma=gamma, probability=True, class_weight="balanced", random_state=RANDOM_STATE))
        ])
    else:
        clf = XGBClassifier(
            n_estimators=trial.suggest_int("n_estimators", 50, 300),
            max_depth=trial.suggest_int("max_depth", 3, 12),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3),
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            use_label_encoder=False
        )
    return clf, model_type

def objective(trial, X_train, y_train, X_val, y_val):
    clf, model_type = build_clf_from_trial(trial)
    clf.fit(X_train, y_train)
    preds = clf.predict(X_val)
    return balanced_accuracy_score(y_val, preds)

def train_and_evaluate_optuna(X, y, n_trials=OPTUNA_TRIALS):
    # split for validation to compute threshold
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(lambda t: objective(t, X_train, y_train, X_val, y_val), n_trials=n_trials)

    best_params = study.best_trial.params
    best_model_choice = best_params.get("model", None)
    best_trial = study.best_trial

    def gp(name, default=None):
        return best_trial.params.get(name, default)

    model_type = best_trial.params.get("model", "logreg")
    # Build classifier instance using the selected params
    if model_type == "logreg":
        C = gp("C", 1.0)
        final_clf_val = Pipeline([("scaler", StandardScaler()),
                                  ("clf", LogisticRegression(C=C, solver="liblinear",
                                                             class_weight="balanced", random_state=RANDOM_STATE))])
    elif model_type == "rf":
        n_estimators = int(gp("n_estimators", 100))
        max_depth = int(gp("max_depth", 5))
        final_clf_val = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                               random_state=RANDOM_STATE, class_weight="balanced")
    elif model_type == "svm":
        C = gp("C", 1.0)
        gamma = gp("gamma", "scale")
        final_clf_val = Pipeline([("scaler", StandardScaler()),
                                  ("clf", SVC(C=C, gamma=gamma, probability=True,
                                              class_weight="balanced", random_state=RANDOM_STATE))])
    else:
        n_estimators = int(gp("n_estimators", 100))
        max_depth = int(gp("max_depth", 6))
        learning_rate = float(gp("learning_rate", 0.1))
        final_clf_val = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                      learning_rate=learning_rate, subsample=0.9, colsample_bytree=0.9,
                                      eval_metric="logloss", random_state=RANDOM_STATE, use_label_encoder=False)

    # Fit on train to compute validation metrics and threshold
    final_clf_val.fit(X_train, y_train)
    if hasattr(final_clf_val, "predict_proba"):
        prob = final_clf_val.predict_proba(X_val)[:, 1]
    else:
        # some classifiers may not support predict_proba; approximate with decision function
        if hasattr(final_clf_val, "decision_function"):
            scores = final_clf_val.decision_function(X_val)
            # scale to 0-1 via min-max for ROC thresholding only (not ideal, but works for threshold calc)
            scores_min, scores_max = scores.min(), scores.max()
            prob = (scores - scores_min) / (scores_max - scores_min + 1e-10)
        else:
            prob = final_clf_val.predict(X_val).astype(float)

    fpr, tpr, thr = roc_curve(y_val, prob)
    youden = tpr - fpr
    opt_idx = int(np.argmax(youden))
    opt_thresh = float(thr[opt_idx])

    y_pred = (prob >= opt_thresh).astype(int)

    results_val = {
        "best_trial": best_trial,
        "model_choice": model_type,
        "val_clf": final_clf_val,
        "opt_thresh": opt_thresh,
        "y_val": y_val,
        "y_prob": prob,
        "y_pred": y_pred,
        "report": classification_report(y_val, y_pred, target_names=["Impostor", "Genuine"]),
        "confusion": confusion_matrix(y_val, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_val, y_pred),
        "fpr": fpr, "tpr": tpr, "roc_auc": auc(fpr, tpr)
    }

    # Recreate the final estimator with same configuration (identical to final_clf_val), fit on full X
    final_clf_full = None
    if model_type == "logreg":
        C = gp("C", 1.0)
        final_clf_full = Pipeline([("scaler", StandardScaler()),
                                   ("clf", LogisticRegression(C=C, solver="liblinear",
                                                              class_weight="balanced", random_state=RANDOM_STATE))])
    elif model_type == "rf":
        n_estimators = int(gp("n_estimators", 100))
        max_depth = int(gp("max_depth", 5))
        final_clf_full = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                                random_state=RANDOM_STATE, class_weight="balanced")
    elif model_type == "svm":
        C = gp("C", 1.0)
        gamma = gp("gamma", "scale")
        final_clf_full = Pipeline([("scaler", StandardScaler()),
                                   ("clf", SVC(C=C, gamma=gamma, probability=True,
                                               class_weight="balanced", random_state=RANDOM_STATE))])
    else:
        n_estimators = int(gp("n_estimators", 100))
        max_depth = int(gp("max_depth", 6))
        learning_rate = float(gp("learning_rate", 0.1))
        final_clf_full = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                       learning_rate=learning_rate, subsample=0.9, colsample_bytree=0.9,
                                       eval_metric="logloss", random_state=RANDOM_STATE, use_label_encoder=False)

    final_clf_full.fit(X, y)

    # Extract scaler if available (pipeline with named_steps)
    scaler_obj = None
    try:
        if isinstance(final_clf_full, Pipeline):
            if "scaler" in final_clf_full.named_steps:
                scaler_obj = final_clf_full.named_steps["scaler"]
    except Exception:
        scaler_obj = None

    results_val["final_model"] = final_clf_full
    results_val["scaler"] = scaler_obj

    return results_val

# =====================================================
# 📊 Visualization
# =====================================================
def plot_confusion(cm, out="confusion_matrix.png"):
    plt.figure(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=["Impostor (Pred)", "Genuine (Pred)"],
                yticklabels=["Impostor (Actual)", "Genuine (Actual)"])
    plt.title("Confusion Matrix")
    plt.ylabel("Actual")
    plt.xlabel("Predicted")
    plt.savefig(out)
    plt.close()

def plot_roc(fpr, tpr, roc_auc, out="roc_curve.png"):
    plt.figure(figsize=(6,5))
    plt.plot(fpr, tpr, lw=2, label=f"AUC = {roc_auc:.4f}")
    plt.plot([0,1],[0,1],'--')
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend()
    plt.savefig(out)
    plt.close()

def plot_score_dist(probs, labels, thr, out="score_dist.png"):
    pos = probs[np.array(labels)==1]
    neg = probs[np.array(labels)==0]
    plt.figure(figsize=(10,6))
    sns.histplot(neg, kde=True, label="Impostor", bins=50)
    sns.histplot(pos, kde=True, label="Genuine", bins=50)
    plt.axvline(thr, color="blue", linestyle="--", label=f"Threshold={thr:.4f}")
    plt.title("Score Distribution")
    plt.legend()
    plt.savefig(out)
    plt.close()

if __name__ == "__main__":
    random.seed(RANDOM_STATE)
    np.random.seed(RANDOM_STATE)

    print("Loading cached embeddings...")
    embedding_maps = load_embedding_maps(EMBEDDING_CACHE_FILE)

    print("Computing adaptive thresholds...")
    thresholds = auto_sweep_thresholds(embedding_maps, FACES_DIR)
    print(f"Per-model heuristic thresholds: {thresholds}")

    print("Creating image pairs...")
    genuine_pairs, impostor_pairs = create_pairs_from_dir(FACES_DIR, MAX_PAIRS_PER_TYPE, MAX_PAIRS_PER_TYPE)
    if not genuine_pairs or not impostor_pairs:
        raise SystemExit("Error: Not enough pairs to train.")

    print("Preparing dataset...")
    X, y, meta = prepare_dataset(genuine_pairs, impostor_pairs, embedding_maps, thresholds)
    if X.shape[0] < 50:
        raise SystemExit(f"Too few valid pairs ({X.shape[0]}) to train.")

    print(f"Dataset prepared: {X.shape[0]} pairs, {X.shape[1]} features each.")

    print("Running Optuna optimization...")
    results = train_and_evaluate_optuna(X, y, n_trials=OPTUNA_TRIALS)

    metadata = {
        "model": results["final_model"],
        "threshold": float(results["opt_thresh"]),
        "balanced_accuracy": float(results["balanced_accuracy"]),
        "roc_auc": float(results["roc_auc"]),
        "report": results["report"],
        "models_used": MODELS_TO_USE,
        "embedding_cache": EMBEDDING_CACHE_FILE,
        "distance_metric": DISTANCE_METRIC,
        "thresholds_per_model": thresholds,
        "random_state": RANDOM_STATE,
        "scaler": results.get("scaler", None)  
    }

    joblib.dump(metadata, MODEL_FILE)
    print(f"\n Saved trained model and metadata -> {MODEL_FILE}")

    # =====================================================
    # Save evaluation plots from validation stage
    plot_confusion(results["confusion"])
    plot_roc(results["fpr"], results["tpr"], results["roc_auc"])
    plot_score_dist(results["y_prob"], results["y_val"], results["opt_thresh"])

    print("\n Training completed successfully.")
    print(f"Balanced Accuracy (val): {results['balanced_accuracy']:.4f}")
    print(f"ROC AUC (val): {results['roc_auc']:.4f}")
    print("\nClassification Report (val):\n", results["report"])
    print("Plots saved: confusion_matrix.png, roc_curve.png, score_dist.png")
