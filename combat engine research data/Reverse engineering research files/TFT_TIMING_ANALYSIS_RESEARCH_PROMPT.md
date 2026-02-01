# Deep Research Prompt: TFT Combat Timing Analysis & Error Propagation Quantification

---

## Research Objective

I am building a deterministic combat simulator for Teamfight Tactics (TFT) to generate synthetic training data for machine learning models. The simulator must accurately replicate the game's tick-based combat system (30 ticks/second) to achieve >85% fight outcome prediction accuracy.

**Core Problem:** Riot Games does not publish the internal timing constants that govern combat mechanics. These values must be reverse-engineered through empirical measurement. I need to understand:

1. The optimal methodology for measuring these constants
2. How measurement errors propagate through a discrete-event simulation
3. Which constants have the highest sensitivity (largest impact on outcomes)
4. The statistical framework for validating measurement accuracy

---

## Background Context

### What I'm Measuring

| Constant Category | Examples | Suspected Range |
|-------------------|----------|-----------------|
| **Attack Timing** | Windup duration, backswing/recovery, attack speed scaling | 0.1s - 0.8s per attack cycle |
| **Movement** | Walk speed (hexes/second), acceleration, turn rate | 1.5 - 3.0 hexes/second |
| **Ability Casting** | Cast point (mana threshold to damage), channel durations, cast backswing | 0.05s - 2.0s |
| **Projectiles** | Travel speed, homing behavior, collision radius | 5 - 30 hexes/second |
| **State Transitions** | Target acquisition delay, retargeting latency, aggro transfer time | 0 - 0.2s |

### The Simulation Model

TFT combat operates as a discrete-event simulation:
- **Tick rate:** 30 Hz (33.33ms per tick)
- **Deterministic:** Given the same initial state and RNG seed, combat produces identical results
- **State machine:** Each unit cycles through states: `IDLE → ACQUIRING_TARGET → MOVING → ATTACK_WINDUP → ATTACK_RESOLVE → CASTING → IDLE`

### Current Measurement Approach

I plan to use high-framerate video analysis (60 FPS recording in Practice Tool) with computer vision to detect:
- Frame when attack animation begins
- Frame when damage number appears
- Frame when unit starts/stops moving
- Frame when ability projectile spawns

**Limitation:** 60 FPS = 16.67ms resolution, while game ticks are 33.33ms. This creates aliasing.

---

## Research Questions

### Category 1: Measurement Methodology

1. **What is the state-of-the-art methodology for reverse-engineering timing constants from real-time strategy games or MOBAs?**
   - Are there academic papers on extracting game engine parameters through observation?
   - What techniques do speedrunning communities use for frame-perfect timing analysis?
   - How do fighting game communities measure frame data (startup, active, recovery frames)?

2. **What recording and analysis setup minimizes measurement error?**
   - Optimal frame rate (60, 120, 240 FPS)?
   - Should I use screen recording or memory reading?
   - Are there tools specifically designed for frame-by-frame game analysis?
   - How do I account for display latency, encoding latency, and vsync?

3. **How do I handle the aliasing problem between my measurement rate (60 FPS) and the game's simulation rate (30 Hz)?**
   - Nyquist theorem implications
   - Interpolation techniques
   - Statistical methods to estimate sub-frame timing from multiple samples

4. **What visual/audio cues are most reliable for detecting state transitions?**
   - Damage numbers vs health bar changes
   - Animation keyframes vs particle effects
   - Sound effect timing vs visual timing
   - Muzzle flash / projectile spawn detection

### Category 2: Error Propagation Mathematics

5. **How do timing errors propagate through a discrete-event simulation?**
   - If I have ±1 frame (±16.67ms) error on attack windup, how does this compound over a 30-second fight with 20+ attacks?
   - What is the mathematical model for error accumulation in tick-based simulations?
   - Is error propagation linear, multiplicative, or chaotic?

6. **What is the sensitivity of fight outcomes to individual timing parameters?**
   - How do I perform sensitivity analysis on a stochastic simulation?
   - What statistical methods quantify "parameter importance" in complex systems?
   - Are there techniques from uncertainty quantification (UQ) that apply here?

7. **How do I model the interaction between timing errors and game state?**
   - A 50ms error might not matter if units are far apart, but could flip a "race condition" (who casts first)
   - How do I identify and quantify these critical timing thresholds?
   - What's the distribution of "timing-sensitive" vs "timing-insensitive" game states?

8. **What is an acceptable error tolerance for each parameter type?**
   - Is there a threshold below which additional precision yields diminishing returns?
   - How do I calculate the "error budget" across all parameters to achieve a target accuracy?

### Category 3: Validation Framework

9. **How do I validate that my measured constants are correct?**
   - What statistical tests confirm my measurements match ground truth?
   - How many samples do I need per constant for 95% confidence intervals?
   - How do I detect systematic bias in my measurement methodology?

10. **How do I validate the full simulation against real game outcomes?**
    - What metrics beyond "winner accuracy" capture simulation fidelity?
    - How do I isolate timing errors from other error sources (targeting, damage calculation)?
    - What's the expected accuracy ceiling given irreducible measurement uncertainty?

### Category 4: Existing Research & Tools

11. **Are there existing tools or frameworks for game timing analysis?**
    - Frame data extraction tools from fighting games (Street Fighter, Tekken)
    - Speedrun timing tools (LiveSplit, etc.)
    - MOBA-specific analysis tools
    - Computer vision libraries optimized for game footage

12. **Have other researchers reverse-engineered similar game engines?**
    - Dota 2 simulation projects
    - League of Legends damage calculator internals
    - StarCraft Brood War / SC2 bot frameworks (BWAPI, SC2API)
    - Any academic work on "gray-box" game AI that required engine parameter estimation?

13. **What can I learn from physics simulation validation techniques?**
    - How do physics engines validate timestep accuracy?
    - Techniques from numerical methods for ODE/PDE solvers
    - Error analysis in Monte Carlo simulations

---

## Specific Technical Questions

### Attack Timing Deep Dive

14. **How does attack speed modify the attack animation?**
    - Does increased AS compress the entire animation proportionally?
    - Or does it only reduce the "recovery" phase while "windup" stays constant?
    - Is there a minimum animation duration that clips at very high AS?
    - How do I measure the "windup ratio" (% of attack cycle that is windup vs recovery)?

15. **How do I isolate windup from backswing?**
    - Windup = time from attack command to damage dealt
    - Backswing = time from damage dealt to next action possible
    - What visual cues distinguish these phases?
    - Can I use "animation canceling" techniques to measure backswing?

### Movement Deep Dive

16. **Is movement speed constant or does it have acceleration?**
    - Do units accelerate from zero or instantly reach max speed?
    - Is there deceleration / stopping distance?
    - How does pathfinding interact with movement timing?

17. **How do I convert pixel movement to hex-grid distance?**
    - What's the pixel-to-hex calibration for TFT's camera angle?
    - Does the board have consistent hex sizing or perspective distortion?
    - How do I measure diagonal vs orthogonal movement speed?

### Ability Casting Deep Dive

18. **What is the precise definition of "cast point"?**
    - Is it mana threshold reached → damage applied?
    - Or mana threshold → animation start → damage?
    - How do channeled abilities differ from instant casts?
    - What happens if target dies during cast animation?

19. **How do I measure projectile speed and homing behavior?**
    - Linear interpolation vs curved paths?
    - Does homing have a turn rate limit?
    - What's the collision detection radius?

---

## Desired Output Format

Please provide:

1. **Methodology Recommendation**
   - Step-by-step protocol for measuring each constant type
   - Required equipment/software
   - Sample size recommendations
   - Expected time investment

2. **Error Propagation Model**
   - Mathematical framework for quantifying error accumulation
   - Sensitivity coefficients for each parameter type
   - Error budget allocation strategy

3. **Validation Framework**
   - Statistical tests for measurement validation
   - Simulation-to-reality comparison metrics
   - Confidence interval calculations

4. **Literature Review**
   - Relevant academic papers
   - Community resources (fighting game frame data wikis, speedrun documentation)
   - Existing tools and frameworks

5. **Priority Matrix**
   - Which constants to measure first (highest impact per effort)
   - Which constants can be approximated vs must be precise
   - Acceptable error tolerances for each category

---

## Additional Context

### My Constraints
- **No memory reading or client modification** (risk of account ban)
- **External observation only** (screen recording, API data)
- **Budget:** ~40 hours for measurement phase
- **Target accuracy:** 85%+ fight outcome prediction

### My Current Hypotheses
1. Attack windup ratios are ~0.25-0.35 of total attack cycle
2. Walk speed is ~2.0 hexes/second for most units
3. Cast points are ~0.1-0.2 seconds for instant abilities
4. Timing errors <50ms have minimal fight outcome impact
5. Targeting/behavior errors dominate over timing errors

I want this research to either validate or refute these hypotheses with mathematical rigor.

---

## Summary

I need a comprehensive methodology for:
1. **Measuring** TFT combat timing constants through video analysis
2. **Quantifying** how measurement errors propagate through simulation
3. **Validating** that my simulator matches real game behavior
4. **Prioritizing** which constants matter most for prediction accuracy

The goal is to build a simulation accurate enough to generate millions of synthetic training examples for ML models, where the synthetic data distribution closely matches real TFT combat outcomes.

---

*End of Research Prompt*
