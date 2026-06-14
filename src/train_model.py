"""Train baseline LogisticRegression + XGBoost classifier, plus XGBoost goal regressors; save models and print metrics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.feature_engineering import FEATURE_COLUMNS


def eval_classifier(name: str, y_true: np.ndarray, y_prob: np.ndarray, y_pred: np.ndarray) -> None:
    print(f"\n=== {name} ===", file=sys.stderr)
    print(f"Accuracy:  {accuracy_score(y_true, y_pred):.4f}", file=sys.stderr)
    print(f"Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}", file=sys.stderr)
    print(f"Recall:    {recall_score(y_true, y_pred, zero_division=0):.4f}", file=sys.stderr)
    print(f"F1:        {f1_score(y_true, y_pred, zero_division=0):.4f}", file=sys.stderr)
    try:
        print(f"ROC AUC:   {roc_auc_score(y_true, y_prob):.4f}", file=sys.stderr)
    except ValueError:
        print("ROC AUC:   n/a", file=sys.stderr)
    print(f"Log Loss:  {log_loss(y_true, y_prob, labels=[0, 1]):.4f}", file=sys.stderr)
    print(f"Brier:     {brier_score_loss(y_true, y_prob):.4f}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=_ROOT / "data" / "training_dataset.csv",
    )
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--xgb-iters", type=int, default=50, help="RandomizedSearchCV iterations")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    df = df.sort_values("match_id").reset_index(drop=True)
    n = len(df)
    split = int(n * (1.0 - args.test_ratio))
    train, test = df.iloc[:split], df.iloc[split:]

    X_train = train[FEATURE_COLUMNS].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    X_test = test[FEATURE_COLUMNS].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train, y_test = train["target"].values, test["target"].values

    models_dir = _ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # --- Baseline: Logistic Regression + calibration (scaled) ---
    lr_pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=4000, random_state=args.random_state, solver="lbfgs")),
        ]
    )
    lr_cal = CalibratedClassifierCV(lr_pipe, method="isotonic", cv=3)
    lr_cal.fit(X_train, y_train)
    p_lr = lr_cal.predict_proba(X_test)[:, 1]
    pred_lr = (p_lr >= 0.5).astype(int)
    eval_classifier("LogisticRegression (calibrated)", y_test, p_lr, pred_lr)
    joblib.dump(lr_cal, models_dir / "logistic_regression.pkl")

    # --- XGBoost + RandomizedSearchCV (time-series CV) ---
    xgb = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=args.random_state,
        n_jobs=-1,
    )
    param_dist = {
        "n_estimators": [100, 200, 300, 400],
        "max_depth": [3, 4, 5, 6, 8],
        "learning_rate": [0.01, 0.03, 0.05, 0.1, 0.15],
        "subsample": [0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
        "min_child_weight": [1, 3, 5],
    }
    tscv = TimeSeriesSplit(n_splits=5)
    search = RandomizedSearchCV(
        xgb,
        param_distributions=param_dist,
        n_iter=args.xgb_iters,
        scoring="neg_log_loss",
        cv=tscv,
        random_state=args.random_state,
        n_jobs=-1,
        verbose=1,
    )
    search.fit(X_train, y_train)
    best: XGBClassifier = search.best_estimator_
    p_xgb = best.predict_proba(X_test)[:, 1]
    pred_xgb = (p_xgb >= 0.5).astype(int)
    eval_classifier("XGBoost (best CV)", y_test, p_xgb, pred_xgb)
    print(f"Best params: {search.best_params_}", file=sys.stderr)
    joblib.dump(best, models_dir / "xgboost_model.pkl")

    # --- Goal regressors (same features; XGBoost only — used for expected-goals in UI) ---
    if "home_goals" in train.columns and "away_goals" in train.columns:
        yh_train, yh_test = train["home_goals"].astype(float).values, test["home_goals"].astype(float).values
        ya_train, ya_test = train["away_goals"].astype(float).values, test["away_goals"].astype(float).values

        reg_params = dict(
            objective="reg:squarederror",
            n_estimators=400,
            max_depth=5,
            learning_rate=0.06,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=2,
            random_state=args.random_state,
            n_jobs=-1,
        )
        reg_home = XGBRegressor(**reg_params)
        reg_away = XGBRegressor(**reg_params)
        reg_home.fit(X_train, yh_train)
        reg_away.fit(X_train, ya_train)
        ph, pa = reg_home.predict(X_test), reg_away.predict(X_test)
        print("\n=== Goal regressors (XGBRegressor) ===", file=sys.stderr)
        print(f"Home goals MAE: {mean_absolute_error(yh_test, ph):.3f}", file=sys.stderr)
        print(f"Away goals MAE: {mean_absolute_error(ya_test, pa):.3f}", file=sys.stderr)
        print(f"Home goals RMSE: {float(np.sqrt(mean_squared_error(yh_test, ph))):.3f}", file=sys.stderr)
        print(f"Away goals RMSE: {float(np.sqrt(mean_squared_error(ya_test, pa))):.3f}", file=sys.stderr)
        joblib.dump(reg_home, models_dir / "xgboost_goals_home.pkl")
        joblib.dump(reg_away, models_dir / "xgboost_goals_away.pkl")
        print(f"Saved goal models to {models_dir}", file=sys.stderr)
    else:
        print(
            "training_dataset.csv has no home_goals/away_goals — rebuild with dataset_builder, then retrain.",
            file=sys.stderr,
        )

    print(f"Saved models to {models_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
