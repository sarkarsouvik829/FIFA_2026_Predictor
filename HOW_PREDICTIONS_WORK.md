# How this app’s predictions work

This note is for anyone opening the project or the Streamlit UI who wants a plain-language picture of **what** is being predicted, **from what data**, and **how** win odds and goals are produced—without diving into formulas or code.

---

## What you see in the app

### Match predictor tab

When you pick two countries and click **Predict match**, you get:

1. **Win percentages for Team 1 and Team 2**  
   These are the model’s estimate of how likely each side is to **win the match outright**. The app does **not** show a draw probability today: training only uses matches that had a winner (no draws in the training rows used for the classifier).

2. **“Expected goals” as whole numbers**  
   Two separate models estimate how many goals each team might score in that situation. The app shows the **whole-number part** of each estimate (for example, if the underlying model says about 2.1 goals, you see **2**). Think of it as a rough “how many goals might this team score?” hint, not a guarantee of the final score.

### Monte Carlo tab

That tab runs **many simulated World Cups** using the same style of match prediction inside the simulation. It answers questions like “how often does each country reach the knockouts or win the tournament in these runs?”—not “who will definitely win the real 2026 World Cup.”

---

## What data everything is built on

- **International match history** (who played whom, when, scores, tournament name, neutral venue or not). This is the main **Dataset A** file in `data/`.

- **Team strength over time (Elo-style)** built from that history, stored as **Dataset B**. It gives each team a rating that goes up and down after games so the model can compare “how strong were they *before* this match?” without peeking at the future.

The models only use information that would have been known **before** the match being scored—so predictions for a hypothetical game use history up to the last real match in the file, not future results.

---

## How win % is predicted

- The app turns each matchup into a **small set of numbers** that summarize the situation: things like the gap in team strength (Elo), recent form (wins, goals for/against over recent games), how hard their recent opponents were, how important the competition is (friendly vs World Cup, etc.), and whether the game is neutral.

- A **win/loss classifier** was trained on tens of thousands of past decisive internationals: “did the home team win?” The trained model is saved on disk; you can choose **XGBoost** or **logistic regression** in the UI for this step.

- For your chosen teams, the app feeds the same kind of numbers into that model and reads off **probability of a win for Team 1**; Team 2’s percentage is the remainder so the two add to 100%.

**Important:** this is a statistical model from history, not a crystal ball. Upsets happen; the percentages are guides.

---

## How goals are predicted

- **Separate** from the win model, two **goal** models were trained on the same matches: one tries to predict **home goals**, the other **away goals**, from the same summary numbers (strength, form, schedule, tournament, neutral venue).

- Those models always come from **gradient boosting regression** (saved as the “goals home” and “goals away” files under `models/`), even if you pick logistic regression for **win** probability.

- Internally the model outputs a **decimal** (like an average). The app **drops the fraction** and shows only the **integer part** so the display reads like whole goals.

Goals and win % are **not forced to agree** (for example, you could in principle see a high win chance but modest goal numbers); they are two different questions answered by two different trained pieces.

---

## World Cup 2026 simulation (Monte Carlo)

The simulator uses the **official-style 2026 group and knockout structure** from your fixture data, runs random outcomes for groups and ties where the rules need it, and uses the **match win model** to decide who advances in each knockout game. After thousands of runs, it counts how often each nation reaches each stage.

Long runs take time on a normal PC; the app can use a smaller number of simulations for a quicker feel.

---

## How to refresh models after updating data

If you change or extend the match CSV and rebuild training data, you need to **retrain** so the files in `models/` match the new history. Typical order: build historical Elo → build training table → run training (see `README.md`). Until goal models exist, the UI may show win % only and skip the goal line.

---

## Where to look next

- **`README.md`** — how to install, run the app, and run the pipeline from the command line.  
- **`requirement.md`** — detailed project spec (more technical).  
- **`src/predict_match.py`** — entry point for a single match prediction from code or CLI.

If something in the UI disagrees with intuition, remember: the numbers are **model outputs from past patterns**, not official FIFA forecasts.
