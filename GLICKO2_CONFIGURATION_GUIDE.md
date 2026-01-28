# Glicko-2 Rating System Configuration Guide

## Overview

This document provides a comprehensive reference for all configurable parameters in the Glicko-2 rating system. All parameters are stored in `glicko2_config.json` and can be tuned without code changes.

---

## Configuration Structure

```json
{
  "glicko2": { /* Core Glicko-2 parameters */ },
  "rating_scaling": { /* Advanced rating-based scaling */ },
  "description": { /* Human-readable descriptions */ }
}
```

---

## Part 1: Core Glicko-2 Parameters

These parameters control the fundamental Glicko-2 rating calculations.

### 1.1 `initial_rating` (default: 1500.0)

**What it does:**
- Starting rating for all new players
- The "baseline" or "average" rating

**Range:** 1000 - 2000  
**Recommended:** 1500.0

**Impact:**
- Higher: New players start with higher ratings
- Lower: New players start with lower ratings

**Synergy:**
- Works with `rating_sensitivity` in rating-based scaling to determine "below/above average"

---

### 1.2 `initial_rd` (default: 175.0)

**What it does:**
- Starting Rating Deviation (uncertainty) for new players
- Higher RD = more volatile rating changes
- RD decreases over time as players play more games

**Range:** 100 - 350  
**Recommended:** 150 - 200

**Impact:**
- **Higher (250+):** New players' ratings swing wildly in first ~20 games
- **Lower (100-150):** More stable, gradual rating changes even for new players

**Synergy:**
- Interacts heavily with `rd_baseline_correction` and `rd_correction_winner_factor`
- Sets the starting point for how quickly players "settle" into their true rating

**Trade-offs:**
- High RD = Faster convergence to true skill, but more chaotic early ratings
- Low RD = Smoother experience, but slower to reach true rating

---

### 1.3 `initial_sigma` (default: 0.06)

**What it does:**
- Starting volatility parameter
- Controls how much a player's RD can change between games
- Higher sigma = RD can increase more between games (player becoming less predictable)

**Range:** 0.03 - 0.12  
**Recommended:** 0.05 - 0.07

**Impact:**
- **Higher (0.10+):** Ratings can become volatile even for established players if they have surprising results
- **Lower (0.03-0.05):** Ratings remain stable; surprising results have less long-term impact on RD

**Synergy:**
- Works with `tau` to control long-term rating volatility
- Affects how "bouncy" established player ratings can become

**Technical Note:**
Sigma is the system's way of modeling "player skill volatility" - whether a player's true skill is changing over time.

---

### 1.4 `tau` (default: 1.5)

**What it does:**
- System volatility constraint
- Controls how much sigma (volatility) can change based on unexpected results
- Higher tau = larger volatility increases when results are surprising

**Range:** 0.3 - 2.0  
**Recommended:** 1.0 - 1.75

**Impact:**
- **Higher (1.5-2.0):** System reacts strongly to upsets; ratings can swing dramatically
- **Lower (0.3-0.8):** System is conservative; even surprising results don't cause huge changes

**Synergy:**
- Amplifies the effect of `weight_multiplier`
- Works with `initial_sigma` to control overall system volatility

**Real-world meaning:**
- High tau = "Players' skills can change rapidly" (good for learning/improving players)
- Low tau = "Players' skills are mostly fixed" (good for established/stable player pools)

---

### 1.5 `weight_multiplier` (default: 2.25)

**What it does:**
- Multiplier for micromatch weights in team games
- Controls the "effective number of games" each match counts as
- Higher = each game has more impact on ratings

**Range:** 1.0 - 3.0  
**Recommended:** 1.75 - 2.5

**Impact:**
- **Higher (2.5-3.0):** Large rating swings per game; fast convergence
- **Lower (1.0-1.5):** Small rating swings per game; slow, gradual changes

**Synergy:**
- Multiplicative with `tau` - **BOTH high = explosive rating changes**
- Balanced by normalization (zero-sum per game)
- Amplifies the effect of `rating_sensitivity`

**Micromatch mechanics:**
- Red team (7 players): each match is worth `weight_multiplier / 3` (~0.75 at 2.25)
- Black team (3 players): each match is worth `weight_multiplier / 7` (~0.32 at 2.25)

---

### 1.6 `epsilon` (default: 0.000001)

**What it does:**
- Convergence tolerance for iterative calculations
- Technical parameter for numerical stability

**Range:** 0.000001 - 0.00001  
**Recommended:** 0.000001

**Impact:**
- Practically no visible impact on ratings
- Lower = more precise calculations, slightly slower
- Higher = faster calculations, negligible precision loss

**Warning:** Do not change unless you understand numerical methods.

---

## Part 2: Rating-Based Scaling Parameters

These parameters implement a custom layer on top of Glicko-2 to make rating changes more intuitive based on rating differences.

### 2.1 `enabled` (default: true)

**What it does:**
- Master switch for rating-based scaling
- If false, uses pure Glicko-2 without any scaling adjustments

**Values:** true | false

**Impact:**
- `false`: Pure Glicko-2 (rating changes ignore rating difference vs opponents)
- `true`: Rating changes scale based on how much higher/lower you are vs opponents

---

### 2.2 `rating_sensitivity` (default: 220.0)

**What it does:**
- Controls how aggressively rating differences affect scaling
- Lower = more aggressive differentiation
- This is the "divisor" in the scaling formula

**Range:** 200 - 500  
**Recommended:** 220 - 280

**Impact:**
- **Lower (200-240):** Big difference in gains/losses based on rating vs opponents
  - High-rated winners gain very little
  - Low-rated winners gain a lot
- **Higher (300-400):** Smaller difference; rating vs opponents matters less

**Formula:**
```
raw_scaling = 1.0 - (player_rating - opponent_avg_rating) / rating_sensitivity
```

**Example (sensitivity = 220):**
- Player rated 1650 vs avg opponent 1550 (diff = +100):
  - Win: scaling = 1.0 - (100/220) = 0.55 → reduced gain
  - Loss: scaling = 1.0 + (100/220) = 1.45 → increased loss
  
- Player rated 1450 vs avg opponent 1550 (diff = -100):
  - Win: scaling = 1.0 - (-100/220) = 1.45 → increased gain
  - Loss: scaling = 1.0 + (-100/220) = 0.55 → reduced loss

**Synergy:**
- Balanced by `max_scaling` and `min_scaling` (prevents extreme values)
- Works multiplicatively with base Glicko-2 changes
- Amplified by high `weight_multiplier`

---

### 2.3 `rd_dampening` (default: 0.046)

**What it does:**
- Reduces the effect of rating-based scaling for high-RD (uncertain) players
- Prevents the scaling from over-reacting for players with unstable ratings

**Range:** 0.01 - 0.05  
**Recommended:** 0.035 - 0.050

**Impact:**
- **Higher (0.045-0.050):** High-RD players get less scaling benefit/penalty
- **Lower (0.010-0.030):** High-RD players get full scaling effect

**Formula:**
```
rd_excess = max(0, player_rd - rd_baseline_scaling)
rd_factor = 1.0 / (1.0 + rd_excess * rd_dampening)
adjusted_scaling = 1.0 + (raw_scaling - 1.0) * rd_factor
```

**Purpose:**
- Prevents wild swings for new/uncertain players
- Ensures scaling primarily affects established players

---

### 2.4 `max_scaling` (default: 1.70)

**What it does:**
- Maximum multiplier that can be applied to rating changes
- Caps how much rating-based scaling can **increase** a change

**Range:** 1.3 - 2.0  
**Recommended:** 1.6 - 1.75

**Impact:**
- **Higher (1.8-2.0):** Allows very large gains for low-rated winners / losses for high-rated losers
- **Lower (1.3-1.5):** More conservative; limits extreme changes

**Example:**
- Base change from Glicko-2: +10 points
- max_scaling = 1.70
- After scaling: at most +17 points (10 × 1.70)

**Synergy:**
- Must be balanced with `weight_multiplier` (both high = explosive)
- Clamped by normalization (can't break zero-sum)

---

### 2.5 `min_scaling` (default: 0.975)

**What it does:**
- Minimum multiplier that can be applied to rating changes
- Caps how much rating-based scaling can **decrease** a change

**Range:** 0.5 - 1.0  
**Recommended:** 0.85 - 0.98

**Impact:**
- **Higher (0.95-1.0):** Prevents large reductions; high-rated winners still gain reasonable amounts
- **Lower (0.5-0.8):** Allows very small gains for high-rated winners / losses for low-rated losers

**Example:**
- Base change from Glicko-2: +20 points
- min_scaling = 0.975
- After scaling: at least +19.5 points (20 × 0.975)

**Critical for:**
- Preventing high-rated winners from gaining almost nothing
- Preventing low-rated losers from losing almost nothing

**Synergy:**
- Works with `rating_sensitivity` to set the "floor" for protection
- Higher values (0.95+) make the system less extreme

---

### 2.6 `rd_baseline_scaling` (default: 52.0)

**What it does:**
- RD baseline used in `apply_rating_based_scaling()` function
- Players with RD above this get dampened scaling

**Range:** 50 - 55  
**Recommended:** 51 - 53

**Impact:**
- **Lower (50-51):** More players are considered "high RD" and get dampened
- **Higher (53-55):** Fewer players are considered "high RD"; scaling is more aggressive

**Typical RD values:**
- New players: 175 (very high)
- After 10 games: 60-70 (high)
- After 30 games: 50-55 (normal)
- After 100 games: 48-52 (stable)

---

### 2.7 `rd_baseline_correction` (default: 51.0)

**What it does:**
- RD baseline used in `process_game()` for pre-scaling RD correction
- Players with RD above this get their **base Glicko-2 changes** dampened before scaling

**Range:** 50 - 55  
**Recommended:** 50 - 52

**Impact:**
- **Lower (50-51):** More aggressive dampening of high-RD players
- **Higher (53-55):** Less dampening; high-RD players change more

**Purpose:**
- Counteracts Glicko-2's tendency to make high-RD players very volatile
- Applied BEFORE rating-based scaling (acts as a "pre-filter")

**Difference from `rd_baseline_scaling`:**
- `rd_baseline_correction`: Applied to raw Glicko-2 output (first pass)
- `rd_baseline_scaling`: Applied during rating-based scaling (second pass)

---

### 2.8 `rd_correction_winner_factor` (default: 0.045)

**What it does:**
- Strength of RD dampening for **winners**
- Higher = more aggressive dampening of high-RD winners

**Range:** 0.03 - 0.10  
**Recommended:** 0.040 - 0.055

**Impact:**
- **Higher (0.060-0.090):** High-RD winners gain significantly less
  - Example: RD=65 winner might gain 30% less than RD=52 winner
- **Lower (0.020-0.040):** High-RD winners gain almost as much as normal-RD winners

**Formula:**
```
rd_deviation = player_rd - rd_baseline_correction
if is_win and rd_deviation > 0:
    rd_correction_factor = 1.0 / (1.0 + rd_deviation * rd_correction_winner_factor)
    change = change * rd_correction_factor
```

**Example (factor = 0.045, baseline = 51):**
- Player with RD = 52: deviation = 1, factor = 1/(1 + 0.045) = 0.957 → ~4% reduction
- Player with RD = 65: deviation = 14, factor = 1/(1 + 0.630) = 0.613 → ~39% reduction

**Critical for:**
- Preventing new/uncertain players from skyrocketing after lucky wins
- Ensuring rating primarily rewards established players

---

### 2.9 `rd_correction_loser_factor` (default: 0.0005)

**What it does:**
- Strength of RD dampening for **losers**
- Higher = more aggressive dampening of high-RD losers (they lose less)

**Range:** 0.0001 - 0.005  
**Recommended:** 0.0003 - 0.0010

**Impact:**
- **Higher (0.0015-0.005):** High-RD losers are heavily protected; they lose much less
- **Lower (0.0001-0.0005):** High-RD losers get minimal protection; they lose almost normally

**Why asymmetric?**
- Winners get strong dampening (0.045) to prevent inflation
- Losers get weak dampening (0.0005) to ensure accountability
- This creates a system where **being uncertain (high RD) doesn't save you from losses much**

**Example (factor = 0.0005, baseline = 51):**
- Player with RD = 52: deviation = 1, factor = 1/(1 + 0.0005) = 0.9995 → ~0.05% reduction (negligible)
- Player with RD = 67: deviation = 16, factor = 1/(1 + 0.0080) = 0.992 → ~0.8% reduction (small)

**Critical for:**
- Maintaining fairness: high-RD players can't hide behind uncertainty to avoid losses
- Balancing with winner dampening to maintain zero-sum

---

## Part 3: Parameter Synergies and Interactions

### 3.1 Volatility Trio: `tau` + `weight_multiplier` + `rating_sensitivity`

**How they work together:**
1. **`weight_multiplier`** sets the base magnitude of changes
2. **`tau`** amplifies unexpected results
3. **`rating_sensitivity`** scales those changes based on rating differences

**Combinations:**

| tau | weight_mult | sensitivity | Result |
|-----|-------------|-------------|--------|
| High (1.75) | High (2.5) | Low (200) | **Explosive:** Huge swings, fast adaptation |
| High (1.75) | Low (1.5) | Low (200) | **Aggressive scaling:** Moderate swings, strong differentiation |
| Low (1.0) | High (2.5) | High (400) | **Conservative bulk:** Moderate swings, weak differentiation |
| Low (1.0) | Low (1.5) | High (400) | **Glacial:** Tiny changes, slow adaptation |

**Recommended balanced sets:**

**Fast Convergence (for new leagues):**
```json
"tau": 1.75,
"weight_multiplier": 2.5,
"rating_sensitivity": 240
```

**Balanced (current production):**
```json
"tau": 1.5,
"weight_multiplier": 2.25,
"rating_sensitivity": 220
```

**Conservative (for established leagues):**
```json
"tau": 1.25,
"weight_multiplier": 1.75,
"rating_sensitivity": 280
```

---

### 3.2 RD Dampening Chain

The system applies RD-based dampening in two stages:

**Stage 1: Pre-Correction (in `process_game`)**
- Uses `rd_baseline_correction` and `rd_correction_winner/loser_factor`
- Dampens the **raw Glicko-2 output** before any scaling
- Purpose: Prevent base volatility from high-RD players

**Stage 2: Scaling Dampening (in `apply_rating_based_scaling`)**
- Uses `rd_baseline_scaling` and `rd_dampening`
- Dampens the **scaling effect** for high-RD players
- Purpose: Prevent scaling from over-reacting to uncertain players

**Why two stages?**
- Stage 1 controls base magnitude (prevents +50 point swings)
- Stage 2 controls differentiation (prevents 2x scaling on uncertain ratings)
- Together they create stable behavior for new players while still allowing convergence

---

### 3.3 Scaling Bounds: `max_scaling` + `min_scaling` + `rating_sensitivity`

These three work together to create a "scaling window":

```
min_scaling ≤ final_scaling ≤ max_scaling
```

**The window size** = `max_scaling - min_scaling`
- Narrow window (1.5 - 0.9 = 0.6): Limited differentiation
- Wide window (2.0 - 0.5 = 1.5): Extreme differentiation

**The sensitivity** determines how quickly you move within the window:
- Low sensitivity (200): A small rating difference moves you far in the window
- High sensitivity (400): Need a large rating difference to move in the window

**Example:**

```json
"rating_sensitivity": 220,
"max_scaling": 1.70,
"min_scaling": 0.975
```

Rating difference of +220 points:
- Raw scaling = 1.0 - (220/220) = 0.0 → clamped to 0.975 (min)
- Final: gain/loss is multiplied by 0.975

Rating difference of -220 points:
- Raw scaling = 1.0 - (-220/220) = 2.0 → clamped to 1.70 (max)
- Final: gain/loss is multiplied by 1.70

---

## Part 4: Tuning Guidelines

### 4.1 "I want rating changes to be bigger/smaller overall"

**To increase all changes:**
1. Increase `weight_multiplier` (+0.25 per step)
2. OR increase `tau` (+0.25 per step)
3. OR increase `max_scaling` / decrease `min_scaling`

**To decrease all changes:**
1. Decrease `weight_multiplier` (-0.25 per step)
2. OR decrease `tau` (-0.25 per step)
3. OR decrease `max_scaling` / increase `min_scaling`

---

### 4.2 "I want more/less differentiation based on rating"

**To increase differentiation:**
1. Decrease `rating_sensitivity` (-20 per step)
2. OR increase `max_scaling` / decrease `min_scaling`

**To decrease differentiation:**
1. Increase `rating_sensitivity` (+20 per step)
2. OR decrease `max_scaling` / increase `min_scaling`

---

### 4.3 "I want high-RD (new) players to be more/less volatile"

**To make new players more volatile:**
1. Increase `initial_rd` (+25 per step)
2. Decrease `rd_correction_winner_factor` (-0.010 per step)
3. Decrease `rd_dampening` (-0.005 per step)

**To make new players less volatile:**
1. Decrease `initial_rd` (-25 per step)
2. Increase `rd_correction_winner_factor` (+0.010 per step)
3. Increase `rd_dampening` (+0.005 per step)

---

### 4.4 "High-rated players should gain less / lose more"

**This is controlled by:**
1. Lower `rating_sensitivity` (makes scaling more aggressive)
2. Lower `min_scaling` (allows more reduction of gains)
3. Higher `max_scaling` (allows more amplification of losses)

**Current production values achieve this well:**
```json
"rating_sensitivity": 220.0,
"max_scaling": 1.70,
"min_scaling": 0.975
```

---

### 4.5 "Low-rated players should gain more / lose less"

**This is the inverse of 4.4 and is automatically handled by:**
- The same `rating_sensitivity` / `min_scaling` / `max_scaling` settings
- The scaling formula inverts for players below opponent average

---

## Part 5: Current Production Configuration

```json
{
  "glicko2": {
    "initial_rating": 1500.0,
    "initial_rd": 175.0,
    "initial_sigma": 0.06,
    "tau": 1.5,
    "weight_multiplier": 2.25,
    "epsilon": 0.000001
  },
  "rating_scaling": {
    "enabled": true,
    "rating_sensitivity": 220.0,
    "rd_dampening": 0.046,
    "max_scaling": 1.70,
    "min_scaling": 0.975,
    "rd_baseline_scaling": 52.0,
    "rd_baseline_correction": 51.0,
    "rd_correction_winner_factor": 0.045,
    "rd_correction_loser_factor": 0.0005
  }
}
```

**Characteristics:**
- **Moderately aggressive** overall changes (tau=1.5, weight=2.25)
- **Strong differentiation** by rating (sensitivity=220)
- **Balanced bounds** (max=1.70, min=0.975)
- **Strong winner dampening** for high-RD (factor=0.045)
- **Minimal loser dampening** for high-RD (factor=0.0005)

**Result:**
- Established players (RD~50): Changes scale strongly with rating vs opponents
- New players (RD~175): Winners get heavily dampened, losers get minimal protection
- High-rated winners: Small gains (×0.975 to ×1.0)
- Low-rated winners: Large gains (×1.50 to ×1.70)
- High-rated losers: Large losses (×1.50 to ×1.70)
- Low-rated losers: Small losses (×0.975 to ×1.0)

---

## Part 6: Common Pitfalls

### 6.1 "I changed one parameter but nothing happened"

**Likely causes:**
1. The parameter is being clamped by `max_scaling` or `min_scaling`
2. Another parameter is counteracting your change (e.g., high `rd_dampening` negating low `rating_sensitivity`)
3. The change is too small to be visible in single games (try ±0.5 or more)

### 6.2 "Ratings are exploding/deflating"

**Likely causes:**
1. `tau` and `weight_multiplier` are both too high (try reducing one)
2. `max_scaling` is too high (try 1.5-1.7)
3. Normalization is disabled (should never happen in production)

**Fix:**
- Reduce `weight_multiplier` by 0.5
- Reduce `tau` by 0.25
- Ensure zero-sum normalization is working (check "Total Rating Change" in logs)

### 6.3 "High-RD players are still too volatile"

**Likely causes:**
1. `rd_correction_winner_factor` is too low (try 0.055-0.070)
2. `initial_rd` is too high (try 150-175)
3. `rd_dampening` is too low (try 0.045-0.055)

### 6.4 "Rating changes seem random / not based on rating difference"

**Likely causes:**
1. `rating_sensitivity` is too high (try 200-240)
2. `max_scaling` and `min_scaling` are too close together (need at least 0.6 difference)
3. Rating-based scaling is disabled (`enabled: false`)

---

## Part 7: Testing Changes

**Before deploying configuration changes:**

1. **Run simulations** with test data
2. **Check key ratios:**
   - High-RD loser vs normal-RD loser (target: 1.75-1.82x)
   - Low-rated winner vs high-rated winner (target: >1.5x difference)
   - High-RD winner dampening vs normal-RD winner
3. **Verify zero-sum:** Total rating change per game = 0
4. **Test edge cases:**
   - Extreme rating differences (±300 points)
   - Very high RD (>100)
   - Very low RD (<45)

---

## Summary

The Glicko-2 rating system with rating-based scaling has **15 tunable parameters** organized into two groups:

**Core Glicko-2 (6 params):** Control base rating calculations
**Rating Scaling (9 params):** Add intuitive rating-based differentiation

**Key principles:**
1. Changes are **zero-sum** per game (normalization)
2. Changes scale based on **rating vs opponents** (rating_sensitivity)
3. Changes are dampened for **high-RD players** (RD correction)
4. Changes are bounded by **max/min scaling** (safety limits)

**For most tuning needs:**
- Adjust `rating_sensitivity` for differentiation strength
- Adjust `weight_multiplier` for overall change magnitude
- Adjust `rd_correction_winner_factor` for new player volatility
- Keep `min_scaling` high (0.95+) to prevent extreme cases

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-28  
**Production Config Version:** glicko2_config.json (current)

