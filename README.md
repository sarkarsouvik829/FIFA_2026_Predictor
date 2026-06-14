# FIFA 2026 World Cup prediction (Elo + match history)

## Setup

```bash
pip install -r requirements.txt
```

## Data

- **Dataset A**: `python fetch_dataset_a.py` → `data/dataset_A_international_matches.csv`
- **Dataset B (historical Elo)**: `python build_historical_elo.py` → `data/dataset_B_historical_elo.csv`

## Pipeline

```bash
python run_pipeline.py                    # Elo + training CSV + train + 100k MC (slow)
python run_pipeline.py --mc-quick         # MC with 1000 sims
python run_pipeline.py --skip-elo --skip-train   # MC only (needs prior artifacts)
```

## Models & training

```bash
python -m src.dataset_builder
python -m src.train_model --xgb-iters 50
```

Models are saved under `models/` (`logistic_regression.pkl`, `xgboost_model.pkl`). After rebuilding the training CSV, training also writes **expected-goals** regressors: `xgboost_goals_home.pkl` and `xgboost_goals_away.pkl` (used by the UI and `predict_match` regardless of whether you pick logistic or XGBoost for win probability).

## CLI match prediction

```bash
python -m src.predict_match Argentina France 2026-06-11 "FIFA World Cup" 1
```

## Monte Carlo

```bash
python -m src.monte_carlo -n 100000 -o outputs/monte_carlo_results.csv
```

Full tournament simulation is CPU-heavy (~1–2 simulations/sec depending on hardware); 100k runs may take many hours. Use `--quick` for smoke tests.

## Streamlit

```bash
python app.py
# or
streamlit run src/app.py
```

Finished group-stage matches load **live full-time scores** from ESPN’s public World Cup JSON API on each run (merged with `data/wc_app_cache.json`). The banner under the title reports **match result**, **exact scoreline**, and **goal difference** accuracy (see in-app rules under each prediction).

**`data/wc_app_cache.json`** stores FT lines and model outputs so repeat visits can hydrate the UI quickly; predictions for a fixture are skipped if already cached until you clear that entry from the file.

## Understanding what the app predicts

See **[HOW_PREDICTIONS_WORK.md](HOW_PREDICTIONS_WORK.md)** for a short, non-technical explanation of win %, goals, data sources, and Monte Carlo—useful for newcomers or stakeholders.

## Layout

See `requirement.md` for feature definitions. Implemented modules live under `src/` per the plan.
