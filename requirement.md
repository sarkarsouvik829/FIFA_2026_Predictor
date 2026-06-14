# FIFA 2026 World Cup Prediction System

## Project Goal

Build an end-to-end machine learning system that predicts FIFA World Cup match outcomes using historical international football results and Elo ratings.

The system should:

1. Learn team strength from historical matches.
2. Predict the probability of Team A beating Team B.
3. Simulate the FIFA 2026 World Cup tournament.
4. Run 100,000 Monte Carlo simulations.
5. Estimate probabilities of:

   * Reaching Round of 16
   * Reaching Quarter Finals
   * Reaching Semi Finals
   * Reaching Final
   * Winning the World Cup

The initial version must use only:

* Historical International Match Results Dataset
* Historical Elo Ratings Dataset

No squad value, manager, injury, or player-level data is required for V1.

---

# Dataset Inputs

## Dataset A - Historical Match Results

Fields:

* date
* home_team
* away_team
* home_score
* away_score
* tournament
* neutral

---

## Dataset B - Historical Elo Ratings

Fields:

* date
* team
* elo_rating

The Elo dataset must contain ratings that allow retrieval of a team's Elo on any historical date.

---

# Data Processing Requirements

## Chronological Processing

All feature generation must be chronological.

For any match on date D:

Features must be calculated only using information available before D.

Future information must never be used.

This prevents data leakage.

---

# Training Dataset Construction

Create one training record per match.

Example:

Match:
Argentina vs France

Training Row:

{
"features": {...},
"target": 1
}

Target:

1 = Team A wins

0 = Team A does not win

For V1, exclude draws from training.

Future versions may support:

* Win
* Draw
* Loss

classification.

---

# Feature Engineering

All features must be computed separately for both teams and then converted into difference features.

Example:

elo_diff = argentina_elo - france_elo

This allows the model to learn relative strength.

---

## Feature Group A - Elo Features

### Current Elo Difference

Feature Name:

elo_diff

Formula:

team_a_current_elo - team_b_current_elo

---

### Elo Trend (90 Days)

Feature Name:

elo_trend_90_diff

Formula:

## (team_a_current_elo - team_a_elo_90_days_ago)

(team_b_current_elo - team_b_elo_90_days_ago)

Measures recent improvement or decline.

---

### Elo Trend (365 Days)

Feature Name:

elo_trend_365_diff

Measures long-term trajectory.

---

### Peak Elo Difference

Feature Name:

peak_elo_2y_diff

Difference between highest Elo achieved during previous 2 years.

---

# Feature Group B - Recent Form

Use only matches played before current match date.

---

### Win Percentage Last 5 Matches

Feature Name:

win_pct_5_diff

---

### Win Percentage Last 10 Matches

Feature Name:

win_pct_10_diff

---

### Win Percentage Last 20 Matches

Feature Name:

win_pct_20_diff

---

# Feature Group C - Goal Statistics

---

### Goal Difference Last 5 Matches

Feature Name:

goal_diff_5_diff

Formula:

(goals_for - goals_against)

---

### Goal Difference Last 10 Matches

Feature Name:

goal_diff_10_diff

---

### Goal Difference Last 20 Matches

Feature Name:

goal_diff_20_diff

---

### Goals Scored Per Match

Feature Name:

goals_scored_rate_diff

---

### Goals Conceded Per Match

Feature Name:

goals_conceded_rate_diff

---

# Feature Group D - Strength of Schedule

Calculate quality of opponents recently faced.

Opponent quality should be determined using Elo.

---

### Average Opponent Elo Last 10 Matches

Feature Name:

sos_10_diff

---

### Average Opponent Elo Last 20 Matches

Feature Name:

sos_20_diff

---

### Performance Against Strong Teams

Define strong teams as:

elo > 1800

Features:

strong_team_win_pct_diff

strong_team_goal_diff

---

# Feature Group E - Match Context

---

### Tournament Importance

Map tournaments into numeric values.

Example:

World Cup = 5

Continental Championship = 4

World Cup Qualifier = 3

Nations League = 2

Friendly = 1

Feature:

tournament_importance

---

### Neutral Venue

Feature:

neutral

Values:

1 = neutral venue

0 = not neutral

---

# Final Feature List

The final training dataset should contain:

elo_diff

elo_trend_90_diff

elo_trend_365_diff

peak_elo_2y_diff

win_pct_5_diff

win_pct_10_diff

win_pct_20_diff

goal_diff_5_diff

goal_diff_10_diff

goal_diff_20_diff

goals_scored_rate_diff

goals_conceded_rate_diff

sos_10_diff

sos_20_diff

strong_team_win_pct_diff

strong_team_goal_diff

tournament_importance

neutral

target

---

# Model Training Requirements

## Baseline Model

Train Logistic Regression.

Purpose:

* Establish baseline performance.
* Produce calibrated probabilities.

---

## Main Model

Train XGBoost classifier.

Requirements:

* Probability output
* Hyperparameter tuning
* Cross validation

---

# Evaluation Metrics

Calculate:

* Accuracy
* Precision
* Recall
* F1 Score
* ROC AUC
* Log Loss
* Brier Score

Primary metrics:

* Log Loss
* Brier Score

because probability quality is more important than classification accuracy.

---

# Match Prediction Module

Create a reusable prediction API.

Input:

Team A

Team B

Match Date

Output:

{
"team_a": "Argentina",
"team_b": "France",
"team_a_win_probability": 0.58,
"team_b_win_probability": 0.42
}

The module should automatically compute all required features before generating predictions.

---

# Tournament Simulation Engine

Create a tournament simulator.

Input:

* Teams
* Groups
* Tournament structure
* Trained model

Responsibilities:

1. Simulate every group-stage match.
2. Determine group standings.
3. Advance qualified teams.
4. Simulate knockout rounds.
5. Produce tournament winner.

---

# Monte Carlo Simulation

Create a Monte Carlo engine.

Requirements:

Run:

100,000 tournament simulations

For every team track:

* Round of 16 appearances
* Quarter Final appearances
* Semi Final appearances
* Final appearances
* Championships won

Store cumulative counts.

Convert counts to probabilities.

---

# Final Outputs

Generate:

## Team Progression Probabilities

Columns:

team

round_of_16_probability

quarter_final_probability

semi_final_probability

final_probability

champion_probability

---

## Champion Rankings

Sorted descending by:

champion_probability

---

# Code Requirements

The solution must be modular.

Modules:

feature_engineering.py

elo_features.py

form_features.py

schedule_strength.py

dataset_builder.py

train_model.py

predict_match.py

tournament_simulator.py

monte_carlo.py

app.py

---

# Application Requirements

Provide a simple interface.

Option 1:

CLI

Example:

predict Argentina France

Output:

Argentina Win Probability: 58%

France Win Probability: 42%

---

Option 2:

Streamlit Application

Features:

1. Select Team A.
2. Select Team B.
3. Predict match probabilities.
4. Run FIFA 2026 simulation.
5. Display top contenders.
6. Display Semi Final probabilities.
7. Display Final probabilities.
8. Display Champion probabilities.
9. Export results to CSV.

---

# Success Criteria

The application should:

1. Train successfully using historical match and Elo data.
2. Produce calibrated match win probabilities.
3. Simulate complete FIFA World Cup tournaments.
4. Execute 100,000 Monte Carlo simulations.
5. Produce team progression probabilities and championship odds.
6. Be fully reproducible from the provided datasets.
