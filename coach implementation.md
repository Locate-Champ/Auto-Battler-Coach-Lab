
Goal:
Build a TFT coaching layer that can recommend actions at decision time (shop, items, positioning, econ), without pretending you can learn “optimal policies” from end-of-game summaries.

The key design shift
Instead of “each bandit learns actions from inferred labels and final placement reward”, we do:

1. Generate a small set of legal, sensible candidate actions for the current decision type.
2. Apply each action with a deterministic executor to get candidate next-states.
3. Score each candidate next-state using:

   * Combat simulator (tempo, immediate strength)
   * A learned evaluator trained from your final-snapshot dataset (board quality signal)
   * A comp/archetype prior built from high-elo finals (what this board is trying to become)
   * Simple econ math (gold, interest, HP risk)
4. Pick the best-scoring action, and explain why in human terms.

This is “planning with a critic”, not MuZero. No environment model for the full game, no long rollouts required, and no fake “bandit tuples” created from final snapshots.

High-level architecture
GameState (live state) → CandidateGenerator(decision) → Executor(action) → Scorer(next_state) → Recommendation + Explanation

You’ll still keep the 4 decision modules:

* Shop module
* Item module
* Position module
* Econ/Level module

But they won’t be trained as standalone bandits from implied actions. They’ll be action generators + search + scoring.

1) Coach orchestration

coach.py: The runtime entry point. Given a live GameState, it calls the relevant decision module (shop/items/position/econ), asks for candidates, executes them into next-states, scores them, and returns the top 1–3 recommendations.

weights.py: The scoring weights and calibration knobs live here (tempo vs long-term vs econ vs archetype alignment). This is also where you keep any “stage-aware” weight tweaks.

explain.py: Turns score breakdowns into human reasons. This is where you generate output like “+9% winrate in sims” + “keeps 50g interest” + “fits your closest archetype.”

2) Canonical state + rules

state.py: The canonical GameState / UnitState / ItemState definitions. Everyone reads and writes the same structure. Include derived helpers (traits active, interest, etc.) so you don’t recompute them differently across modules.

rules.py: Pure legality and mechanics constraints. “Can this item go here?”, “can I field this many units?”, “what item combos exist from these components?”, etc.

odds.py: Shop odds by level (config-driven). Used by econ lookahead and any roll probability estimates.

pool.py (optional): Champion pool / remaining copies model. Nice-to-have for better roll odds, but you can start with approximations.

encoding.py: Shared encoding functions for ML and scoring (preferably set-based over units, not fixed-slot sorting).

3) One decision module per decision type (each splits into candidates + execute)
Each module should have the same shape:

candidates.py: Generate a small, sane set of candidate actions for the current state.

execute.py: Deterministically apply an action to produce a new GameState.

Concretely:

Shop: candidates are concrete buy/sell/lock/roll plans (not just “BUY_SYNERGY” labels).

Items: candidates are legal slams/assignments/hold choices with a controlled branching factor.

Position: candidates are layouts (templates + small perturbations) that the simulator can compare.

Econ: candidates are save/level/roll-to-X/stabilize lines, optionally evaluated via short-horizon Monte Carlo.

4) Scoring system (this is where “smart” happens)

combat.py: Bridge to your combat simulator. Given (my board, opponent board(s), seeds), return winrate / expected HP delta / whatever your coach uses as “tempo strength.” Add caching + consistent seeding here.

evaluator.py: The learned board evaluator inference code (load model weights, score states). Training can live elsewhere, but the runtime scoring API should be clean and fast.

archetypes.py: The comp/archetype knowledge base. Loads an archetype artifact built from high-elo finals and provides “closest archetypes” + priors (likely carries, typical items, common cores).

features.py: Any shared lightweight feature extraction used by scoring terms (so modules don’t duplicate feature glue).

5) Offline pipeline (turn scraped finals into reusable artifacts)

normalize.py: Raw scraped match history → normalized schema (names converted early, consistent fields).

build_archetypes.py: Cluster normalized final boards into archetypes, then write an artifact your runtime can load (plus summaries like core units/items/traits/top4 rate).

train_evaluator.py: Train the evaluator (ranking model over final snapshots works well with your data situation).

eval_offline.py: Sanity checks and metrics so you know the evaluator/archetypes aren’t garbage.

6) Build/run scripts

build_knowledge_base.py: One command that runs normalization + archetype build, and writes the artifacts used at runtime.

train_models.py: One command that trains the evaluator and saves weights/config.

What this looks like when it “turns out right”

At runtime, the coach doesn’t “predict an action directly from a bandit.” It tries a small set of reasonable actions, simulates and scores the resulting states, then recommends the best one with a clear breakdown.

Items and positioning feel crisp because the simulator is doing the heavy lifting.

Shop and econ feel coherent because archetype alignment + evaluator score + econ math prevent random thrashing.

The offline pipeline produces two core artifacts: an archetype library and an evaluator model, both loadable by the runtime without any training code involved.

GameState fields (minimum useful set)

* stage, round (ex: stage=4, round=2)
* player: level, xp, hp, gold, streak
* board: list[UnitState] with positions
* bench: list[UnitState]
* shop: list[ShopUnit] (if available live)
* items: components + completed items not assigned
* augments: ids (up to 3)
* traits: derived from board (don’t trust scraped trait counts blindly in live mode)
* opponents: optional list of OpponentState (boards you scouted)

UnitState

* champion_id (canonical)
* cost, star
* items: list[item_id]
* position: hex index or (row, col), None if on bench

Encoding: stop doing fixed-slot sorting
The original plan used a “fixed slot ordering sorted by cost then name” for board encoding. That’s a trap: it bakes in arbitrary permutations and makes the model learn weird artifacts.

Use a set-based encoder (DeepSets-ish) that works with “a set of units” and doesn’t care about order.

Sketch:

* Embed champion_id (learned embedding)
* Embed items by summing item embeddings (or average)
* Add star and cost as scalars or embeddings
* Add position embedding only when position matters (positioning module / combat scoring)
* Pass each unit token through a small MLP
* Pool tokens (mean + max concatenated is a solid start)
* Concatenate scalar features (gold, level, hp, stage, streak, interest)
* Concatenate augment embeddings pooled the same way
  Output: a dense context vector for scoring/evaluation.

This encoder is used by the learned evaluator and can also help your heuristics.

The learned evaluator: train what your data can actually support
With final snapshots, the thing you can train reliably is not “what action to take on 3-2”, it’s “how strong is this final-ish board compared to other final-ish boards”.

So train a board evaluator as a ranker, not a policy.

Training data
From each match you have 8 participants with (state_features, placement).

Create pairwise examples inside each lobby:

* For any two players i and j, label which one placed higher.
* Train the model to output a scalar score s(state).
* Optimize a ranking loss (Bradley-Terry / logistic pairwise loss, or margin ranking).

Why ranking beats regression here
Placement numbers aren’t linear, and metas shift. Ranking within the same lobby is a much cleaner signal: “this board beat that board in outcome”.

Evaluator output

* score(state): higher should correlate with better placement
  Optionally:
* top4_head(state): probability of top4 (calibration later)

You will use evaluator(score) inside the planner as one scoring term, not as “the answer”.

Archetype library: make your final snapshots useful at decision time
Final boards are amazing for building a “what are people playing” knowledge base.

Build archetypes by clustering final boards:

* Represent final board as a sparse-ish vector:

  * unit counts weighted by star and cost
  * trait counts
  * key items (carry items)
  * augments
* Cluster (start simple: k-means or HDBSCAN if you know it; k-means works fine if you pick k generously).
* For each archetype:

  * top4 rate / avg placement in your dataset
  * common core units (frequency)
  * common traits
  * item distributions (components → completed item patterns)
  * “carry candidates” (which units most often hold 2-3 items)

At runtime, you compute similarity(current_state, archetype) and use that as:

* a prior for what to buy
* a prior for which items to slam and on whom
* a tie-breaker when multiple actions have similar combat score

Scoring function: one number that can be explained
Each candidate next-state gets a score that’s a weighted sum of interpretable terms.

Example:
score(next_state) =
w_tempo * combat_strength(next_state)

* w_eval  * evaluator_score(next_state)
* w_plan  * plan_value(next_state)          # econ/interest/HP risk
* w_arch  * archetype_alignment(next_state) # “are we coherently building something”

- w_risk  * variance_penalty(next_state)    # optional

combat_strength(next_state)
If you have opponent boards (from scouting), this is straightforward:

* Run simulator next_state vs each likely opponent a few dozen times.
* Get win probability, expected HP delta, or expected round result.
* Aggregate (mean, worst-case, etc.).

If you do not have opponent boards:

* Use a small synthetic opponent set sampled from archetypes at roughly your level/stage (imperfect but better than nothing), or
* Fall back to a simpler internal metric (board value, trait breakpoints, 2-star count).

plan_value(next_state)
This is where econ advice comes from:

* interest next round
* gold remaining after action
* level timing utility (shop odds change)
* HP risk (low HP means you need tempo now)

archetype_alignment(next_state)

* similarity to top-N archetypes given your current units + items + augments
* mild encouragement to commit when you’re already mostly there
* mild discouragement from “random pile of units” unless you’re forced

Modules: how each decision gets candidates and how we score them

1. Item module (this can be very strong with your simulator)
   Candidate generation

* Enumerate all legal item combinations from current components (including “hold”).
* Enumerate a limited set of assignment targets:

  * units on board
  * likely carry/tank candidates (from archetype similarity)
* Generate candidate actions like:

  * Slam item X on unit U
  * Move item (if remover available)
  * Hold components
    Keep the branching factor sane: top 20 to 60 candidates is plenty.

Scoring

* For each candidate next_state, run combat_strength against likely opponent boards.
* Choose the item assignment that improves win chance most, subject to not griefing future (use archetype prior to avoid slamming nonsense).

Explanation you can output

* “This slam increases simulated win chance vs the next likely opponent by +12% and completes a core carry item for your top archetype.”
* “Holding is better because none of the slams meaningfully improve tempo, and you’re one component off a higher-impact item.”

2. Position module (also simulator-friendly)
   Candidate generation

* Start from a few positioning templates (front clump, corner stack, split carries, etc.)
* Add local perturbations (swap 1-2 units, shift carry 1 hex) to avoid brittle templates.

Scoring

* Pure combat simulator: evaluate each layout vs likely opponent(s).
* Optional: add a “robustness” score (performance across multiple opponents, not just one).

Explanation

* “Cornering protects your carry from their assassin line, win rate in sims goes from 41% → 63%.”
* “Spreading frontline reduces AOE value from their Lux/whatever.”

3. Shop module (generate concrete buys, not macro labels)
   You can still think in macro-actions, but implement candidates as actual transaction sets.

Candidate generation ideas
Given shop + current state, generate candidates like:

* Buy immediate upgrade (make 2★/3★) if it exists
* Buy unit that hits next trait breakpoint (especially if it’s a big breakpoint)
* Buy strong standalone unit (cost-weighted + evaluator prior)
* Buy pairs for bench if they’re high-value (carry/tank candidates, or core archetype units)
* Roll N times (where N is small), then do best buys from those rolls (Monte Carlo)
* Do nothing (hold gold)

This should output “action plans” like:

* buy: [A, B], sell: [X], lock_shop: True/False, roll_times: k

Scoring

* Apply the plan to get next_state
* Evaluate:

  * combat_strength (if you made board stronger)
  * plan_value (gold/interest hit)
  * archetype_alignment (are you moving toward a real comp)
  * evaluator_score (board quality signal)

Explanation

* “Buying this pair gives you a 2★ next round with high probability, and it activates 4 Frost, sims improve +8%.”
* “Skipping is correct, shop is low impact and you’d lose an interest breakpoint.”

4. Econ/Level module (short-horizon stochastic lookahead, not vibes)
   This is where you can get “more advanced than heuristics” without going full RL.

Candidate actions

* Save (maintain interest)
* Level now
* Roll down to X gold (ex: to 50, to 30, to 10)
* “Stabilize” line: roll until you hit one upgrade or until you spend Y

Evaluation via short-horizon simulation
You don’t have the full environment, but you do have a good approximation for shop randomness if you model:

* cost odds by level (config)
* unit pool sizes (optional simplification is fine initially)

Do a 1 to 2 round lookahead like:

* For each econ candidate:

  * simulate S shop sequences (ex: S=50 or 100)
  * for each simulated shop, apply your shop-module “best buy plan” greedily
  * after each step, evaluate combat_strength and plan_value
  * average results across samples

This gives you an expected value for “level now vs roll now” that’s actually grounded in probabilities, not just rules of thumb.

Explanation

* “If you roll to 30 here, you have a ~62% chance to hit at least one needed 2★, which boosts your sim win chance enough to protect HP.”
* “Leveling improves shop odds for your targets and doesn’t meaningfully reduce tempo this round.”

Training and build pipeline (no IPS, no fake action labels)
Step 1: normalize scraped data

* Convert names early with your converter
* Create a consistent participant schema with:

  * final board units, items, traits, augments, placement
  * match_id so you can build within-lobby ranking pairs

Step 2: build archetypes

* Vectorize final states
* Cluster
* Save archetype summaries: core units, carry items, trait patterns, top4 rates

Step 3: train evaluator (ranker)

* Build pairwise dataset inside each match
* Train a small MLP over your encoder output, or train end-to-end with the set encoder
* Metrics:

  * pairwise accuracy within lobby
  * Kendall/Spearman rank correlation between predicted score and placement within lobby
  * calibration if you add top4 probability head

Step 4: wire into the planner

* Build scorers
* Tune weights (w_tempo, w_eval, w_plan, w_arch) by simple validation:

  * maximize correlation with placements on held-out finals (for evaluator-only)
  * for live coaching, tune by sanity tests and measured winprob improvements in sims for item/position decisions

Coach interface output (what the user sees)
For each decision type, return:

* Recommended action plan (concrete, executable)
* Top 2 alternatives
* Key numbers that justify it (winprob delta, interest impact, trait breakpoint changes, “fits archetype X”)
* A short plain-language explanation

Implementation order that won’t melt your brain

1. core/state.py + rules.py (canonical state + legality)
2. scoring/combat.py (bridge to simulator + winprob estimator)
3. modules/items (candidate enumeration + sim scoring) because it’ll pay off fast
4. modules/position (templates + sim scoring)
5. training/normalize.py + archetypes.py (make your dataset useful)
6. training/train_evaluator.py (ranker)
7. modules/shop (candidate buys + scoring)
8. modules/econ (short-horizon Monte Carlo)
9. coach/explain.py (make it readable)

Upgrade path if you later get real trajectories
If you eventually capture decision-time snapshots (per round shops, rolls, gold, board, item drops), then you can layer in:

* Behavior cloning policies as priors (predict what high-elo players do)
* Proper contextual bandits (context, action, reward) with real logged contexts
* Offline RL methods that actually make sense with trajectories (IQL/CQL/AWR)
  But you don’t need any of that to ship a coach that feels smart today.

This version is “honest about the data,” leans on your simulator where it’s strongest, and uses learning where it’s actually supported. It’ll also give you way better explanations, which is half the value of a coaching tool anyway.
