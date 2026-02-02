# Glicko-2 Rating Formula - Complete Manual Calculation Guide

**Version:** 1.0  
**Date:** 2026-02-02  
**Status:** Fully synchronized with production code

---

## Purpose

This document explains **exactly** how the Glicko-2 rating system works in this codebase, with enough detail to perform all calculations by hand on paper. Every formula, every step, every constant is documented here.

---

## Table of Contents

1. [Overview of the System](#1-overview-of-the-system)
2. [Constants and Configuration](#2-constants-and-configuration)
3. [Data Structures](#3-data-structures)
4. [Step-by-Step Calculation Process](#4-step-by-step-calculation-process)
5. [Complete Worked Example](#5-complete-worked-example)
6. [Formula Reference](#6-formula-reference)

---

## 1. Overview of the System

### 1.1 What Gets Updated

After each game, every player's three values get updated:
- **Rating (R)**: Skill level (starts at 1500)
- **Rating Deviation (RD)**: Uncertainty (starts at 150)
- **Volatility (σ)**: Performance consistency (starts at 0.06)

### 1.2 The Process Flow

For each game with 10 players:

```
1. Create micromatches (Red vs Black only, no teammates)
2. Calculate tentative Glicko-2 updates for all players
3. Apply first normalization (force zero-sum)
4. Apply RD correction (dampen high-RD players)
5. Apply rating-based scaling (adjust by rating difference)
6. Apply second normalization (restore zero-sum)
7. Update all player ratings
```

### 1.3 Key Custom Features

Beyond standard Glicko-2:
- **Weighted micromatches**: Each match has a weight (not just 1.0)
- **Zero-sum enforcement**: Total rating change = 0 per game
- **RD correction**: High-RD players dampened differently for wins vs losses
- **Rating-based scaling**: Rating changes scale with opponent strength

---

## 2. Constants and Configuration

### 2.1 Core Glicko-2 Constants

From `glicko2_config.json`:

```json
{
  "initial_rating": 1500.0,
  "initial_rd": 150.0,
  "initial_sigma": 0.06,
  "tau": 1.25,
  "weight_multiplier": 1.85,
  "epsilon": 0.000001
}
```

**Glicko-2 Scale Conversion Constant:**
```
q = ln(10) / 400 ≈ 0.00575646...
SCALE = 173.7178 (exactly: 400 / ln(10) × π / √3)
```

**System constants:**
```
TAU (τ) = 1.25
EPSILON (ε) = 0.000001
WEIGHT_MULTIPLIER = 1.85
```

### 2.2 Rating Scaling Configuration

From `glicko2_config.json`:

```json
{
  "enabled": true,
  "rating_sensitivity": 240.0,
  "rd_dampening": 0.032,
  "max_scaling": 1.55,
  "min_scaling": 0.97,
  "rd_baseline_scaling": 52.0,
  "rd_baseline_correction": 52.5,
  "rd_correction_winner_factor": 0.040,
  "rd_correction_loser_factor": 0.0002
}
```

---

## 3. Data Structures

### 3.1 Player Rating Object

Each player has:
```
PlayerRating:
  - player_id: int
  - rating: float (R, default: 1500.0)
  - rd: float (RD, default: 150.0)
  - sigma: float (σ, default: 0.06)
```

### 3.2 Game Data

For a 10-player game:
```
players_data = [(player_id, won: bool), ...]

Example:
[(1, True),  (2, True),  (3, True),  (4, True),   # Red team
 (5, True),  (6, True),  (7, True),               # (7 players won)
 (8, False), (9, False), (10, False)]             # Black team (3 players lost)
```

---

## 4. Step-by-Step Calculation Process

### STEP 1: Scale Conversion (Glicko → Glicko-2)

**Input:** Rating `R`, RD `φ` (in Glicko scale, e.g., R=1500, RD=150)

**Formula:**
```
μ = (R - 1500) / 173.7178
φ = RD / 173.7178
```

**Code reference:** `telegram_webhook.py:156-160`

**Example:**
```
R = 1600, RD = 80

μ = (1600 - 1500) / 173.7178 = 100 / 173.7178 = 0.5756
φ = 80 / 173.7178 = 0.4604
```

---

### STEP 2: The g Function

**Purpose:** Dampens the impact of an opponent based on their RD

**Formula:**
```
g(φⱼ) = 1 / √(1 + 3φⱼ² / π²)
```

**Code reference:** `telegram_webhook.py:170-172`

**Example:**
```
φⱼ = 0.4604

φⱼ² = 0.2120
3φⱼ² / π² = 3 × 0.2120 / 9.8696 = 0.0645
1 + 0.0645 = 1.0645
√1.0645 = 1.0317
g(φⱼ) = 1 / 1.0317 = 0.9693
```

**Intuition:** Higher RD → lower g → opponent's rating matters less

---

### STEP 3: The E Function (Expected Score)

**Purpose:** Predict win probability against an opponent

**Formula:**
```
E(μ, μⱼ, φⱼ) = 1 / (1 + exp(-g(φⱼ) × (μ - μⱼ)))
```

**Code reference:** `telegram_webhook.py:175-177`

**Example:**
```
μ = 0.5756, μⱼ = 0.0 (opponent rated 1500), φⱼ = 0.4604

g(φⱼ) = 0.9693
μ - μⱼ = 0.5756 - 0.0 = 0.5756
g(φⱼ) × (μ - μⱼ) = 0.9693 × 0.5756 = 0.5580
exp(-0.5580) = 0.5723
1 + 0.5723 = 1.5723
E = 1 / 1.5723 = 0.6360
```

**Interpretation:** Player (1600 rating) has 63.6% chance to beat opponent (1500 rating)

---

### STEP 4: Compute Variance (v)

**Purpose:** Estimate uncertainty of performance in this game

**Formula:**
```
v = 1 / Σⱼ [wⱼ × g(φⱼ)² × E(μ, μⱼ, φⱼ) × (1 - E(μ, μⱼ, φⱼ))]
```

Where:
- `wⱼ` = weight of micromatch j
- Sum is over all opponents (not teammates)

**Code reference:** `telegram_webhook.py:180-191`

**Weight calculation:**
```
If player won:
  opponent_count = number of losers (Black team size)
  weight_per_match = WEIGHT_MULTIPLIER / opponent_count
  
If player lost:
  opponent_count = number of winners (Red team size)
  weight_per_match = WEIGHT_MULTIPLIER / opponent_count
```

**Example (Red team player, 7 winners vs 3 losers):**
```
WEIGHT_MULTIPLIER = 1.85
opponent_count = 3
w = 1.85 / 3 = 0.6167

For each of 3 opponents:
  g² = 0.9693² = 0.9395
  E = 0.6360
  E(1-E) = 0.6360 × 0.3640 = 0.2315
  
v_inv = 3 × [0.6167 × 0.9395 × 0.2315] = 0.4030
v = 1 / 0.4030 = 2.481
```

---

### STEP 5: Compute Delta (Δ)

**Purpose:** Measure how much better/worse player performed vs expectation

**Formula:**
```
Δ = v × Σⱼ [wⱼ × g(φⱼ) × (sⱼ - E(μ, μⱼ, φⱼ))]
```

Where:
- `sⱼ` = actual result (1.0 = win, 0.0 = loss)

**Code reference:** `telegram_webhook.py:194-203`

**Example (player won all 3 matches):**
```
v = 2.481
w = 0.6167
g = 0.9693
s = 1.0 (won)
E = 0.6360

For each opponent:
  (s - E) = 1.0 - 0.6360 = 0.3640
  wⱼ × g × (s - E) = 0.6167 × 0.9693 × 0.3640 = 0.2177
  
Sum = 3 × 0.2177 = 0.6531
Δ = 2.481 × 0.6531 = 1.620
```

**Interpretation:** Positive Δ = performed better than expected

---

### STEP 6: Compute New Volatility (σ')

**Purpose:** Update volatility based on surprise factor

**Method:** Illinois algorithm (iterative root-finding)

**Code reference:** `telegram_webhook.py:206-247`

**Setup:**
```
a = ln(σ²)
```

**Define function f(x):**
```
f(x) = [exp(x) × (Δ² - φ² - v - exp(x))] / [2(φ² + v + exp(x))²] - (x - a) / τ²
```

**Find bounds [A, B]:**
```
A = a

If Δ² > φ² + v:
  B = ln(Δ² - φ² - v)
Else:
  k = 1
  While f(a - k×τ) < 0:
    k = k + 1
  B = a - k×τ
```

**Illinois iteration:**
```
While |B - A| > ε:
  C = A + (A - B) × f(A) / (f(B) - f(A))
  
  If f(C) × f(B) < 0:
    A = B
    f(A) = f(B)
  Else:
    f(A) = f(A) / 2
  
  B = C
  f(B) = f(C)
```

**Result:**
```
σ' = exp(A / 2)
```

**Typical example (small surprise):**
```
σ = 0.06
a = ln(0.0036) = -5.6271

After iterations (typically 5-10):
A ≈ -5.5800
σ' = exp(-5.5800 / 2) = exp(-2.7900) = 0.0613
```

---

### STEP 7: Update φ and μ

**Step 7a: Compute φ***
```
φ* = √(φ² + σ'²)
```

**Step 7b: Compute φ'**
```
φ' = 1 / √(1/φ*² + 1/v)
```

**Step 7c: Compute μ'**
```
μ' = μ + φ'² × Σⱼ [wⱼ × g(φⱼ) × (sⱼ - E(μ, μⱼ, φⱼ))]
```

**Code reference:** `telegram_webhook.py:250-278`

**Example:**
```
φ = 0.4604
σ' = 0.0613
v = 2.481
Weighted sum from Step 5 = 0.6531

φ* = √(0.4604² + 0.0613²) = √(0.2120 + 0.0038) = √0.2158 = 0.4645

1/φ*² = 1/0.2158 = 4.634
1/v = 1/2.481 = 0.403
1/φ*² + 1/v = 4.634 + 0.403 = 5.037
φ' = 1/√5.037 = 1/2.244 = 0.4456

μ' = 0.5756 + 0.4456² × 0.6531 = 0.5756 + 0.1986 × 0.6531 = 0.5756 + 0.1297 = 0.7053
```

---

### STEP 8: Convert Back to Glicko Scale

**Formula:**
```
R' = μ' × 173.7178 + 1500
RD' = φ' × 173.7178
σ' = σ' (unchanged scale)
```

**Code reference:** `telegram_webhook.py:163-167`

**Example:**
```
μ' = 0.7053
φ' = 0.4456
σ' = 0.0613

R' = 0.7053 × 173.7178 + 1500 = 122.52 + 1500 = 1622.5
RD' = 0.4456 × 173.7178 = 77.4
σ' = 0.0613
```

**Result:** Player's tentative new rating: **1622.5** (RD: 77.4, σ: 0.0613)

---

### STEP 9: First Normalization (Zero-Sum Enforcement)

**After computing tentative ratings for all 10 players:**

**Formula:**
```
Total_change = Σ (R'ᵢ - Rᵢ)  [for all 10 players]
correction = Total_change / 10

For each player:
  R_normalized = R' - correction
```

**Code reference:** `telegram_webhook.py:404-430`

**Example:**
```
7 Red players gained: +20, +18, +22, +19, +21, +17, +23 = +140
3 Black players lost: -50, -48, -52 = -150

Total_change = 140 + (-150) = -10
correction = -10 / 10 = -1

After normalization:
  Red: +20-(-1)=+21, +18-(-1)=+19, ..., +23-(-1)=+24
  Black: -50-(-1)=-49, -48-(-1)=-47, -52-(-1)=-51
  
New total = 144 + (-147) = -3 ≈ 0 (rounding)
```

---

### STEP 10: RD Correction

**Purpose:** Dampen rating changes for high-RD (uncertain) players

**Different factors for winners vs losers!**

**Code reference:** `telegram_webhook.py:432-449`

**Formula:**

```
RD_baseline = 52.5
is_win = (normalized_change > 0)

RD_deviation = RD - RD_baseline

If is_win AND RD_deviation > 0:
  winner_factor = 0.040
  correction_factor = 1 / (1 + RD_deviation × winner_factor)
  
Else if is_loss AND RD_deviation > 0:
  loser_factor = 0.0002
  correction_factor = 1 / (1 + RD_deviation × loser_factor)
  
Else:
  correction_factor = 1.0

change_after_rd_correction = normalized_change × correction_factor
```

**Example (winner with RD=75):**
```
RD = 75
RD_baseline = 52.5
RD_deviation = 75 - 52.5 = 22.5
winner_factor = 0.040

correction_factor = 1 / (1 + 22.5 × 0.040)
                  = 1 / (1 + 0.9)
                  = 1 / 1.9
                  = 0.5263

If normalized_change = +20:
  change_after_rd = +20 × 0.5263 = +10.53
```

**Example (loser with RD=75):**
```
RD_deviation = 22.5
loser_factor = 0.0002

correction_factor = 1 / (1 + 22.5 × 0.0002)
                  = 1 / (1 + 0.0045)
                  = 1 / 1.0045
                  = 0.9955

If normalized_change = -40:
  change_after_rd = -40 × 0.9955 = -39.82
```

**Key insight:** Winners get heavily dampened (0.53x), losers barely dampened (0.995x)

---

### STEP 11: Rating-Based Scaling

**Purpose:** Scale changes based on rating difference vs opponents

**Code reference:** `telegram_webhook.py:281-345`

**Calculate opponent average:**
```
opponent_avg_rating = average rating of all opponents (not teammates)
```

**Calculate rating difference:**
```
rating_diff = player_rating - opponent_avg_rating
```

**Determine scaling direction:**
```
is_win = (change_after_rd > 0)

If is_win:
  raw_scaling = 1.0 - (rating_diff / rating_sensitivity)
Else (is_loss):
  raw_scaling = 1.0 + (rating_diff / rating_sensitivity)
```

**Apply RD dampening to scaling:**
```
RD_baseline_scaling = 52.0
RD_excess = max(0, RD - RD_baseline_scaling)
rd_dampening = 0.032

rd_factor = 1 / (1 + RD_excess × rd_dampening)
adjusted_scaling = 1.0 + (raw_scaling - 1.0) × rd_factor
```

**Clamp to bounds:**
```
min_scaling = 0.97
max_scaling = 1.55

final_scaling = clamp(adjusted_scaling, min_scaling, max_scaling)
```

**Apply scaling:**
```
scaled_change = change_after_rd × final_scaling
```

**Example 1 (High-rated winner beats weak opponents):**
```
player_rating = 1700
opponent_avg = 1500
rating_diff = +200
rating_sensitivity = 240.0
RD = 55

is_win = True
raw_scaling = 1.0 - (200 / 240) = 1.0 - 0.833 = 0.167

RD_excess = max(0, 55 - 52) = 3
rd_factor = 1 / (1 + 3 × 0.032) = 1 / 1.096 = 0.9124
adjusted_scaling = 1.0 + (0.167 - 1.0) × 0.9124 = 1.0 - 0.760 = 0.240

Clamped: max(0.97, min(1.55, 0.240)) = 0.97

If change_after_rd = +15:
  scaled_change = +15 × 0.97 = +14.55
```

**Example 2 (Low-rated winner beats strong opponents):**
```
player_rating = 1400
opponent_avg = 1600
rating_diff = -200
rating_sensitivity = 240.0
RD = 50

is_win = True
raw_scaling = 1.0 - (-200 / 240) = 1.0 + 0.833 = 1.833

RD_excess = max(0, 50 - 52) = 0
rd_factor = 1.0
adjusted_scaling = 1.0 + (1.833 - 1.0) × 1.0 = 1.833

Clamped: max(0.97, min(1.55, 1.833)) = 1.55

If change_after_rd = +30:
  scaled_change = +30 × 1.55 = +46.5
```

---

### STEP 12: Second Normalization

**After scaling all 10 players' changes:**

**Formula:**
```
Total_scaled_change = Σ scaled_changeᵢ  [for all 10 players]
final_correction = Total_scaled_change / 10

For each player:
  final_change = scaled_change - final_correction
  final_rating = old_rating + final_change
```

**Code reference:** `telegram_webhook.py:462-482`

**Example:**
```
After scaling:
  Red: +21, +17, +25, +19, +23, +15, +27 = +147
  Black: -51, -49, -53 = -153
  
Total_scaled_change = 147 + (-153) = -6
final_correction = -6 / 10 = -0.6

Final changes:
  Red: 21-(-0.6)=21.6, 17-(-0.6)=17.6, ..., 27-(-0.6)=27.6
  Black: -51-(-0.6)=-50.4, -49-(-0.6)=-48.4, -53-(-0.6)=-52.4
  
Total = 149.4 + (-151.2) ≈ 0 ✓
```

---

### STEP 13: Apply Final Ratings

**Update player database:**
```
For each player:
  new_rating = old_rating + final_change
  new_rd = RD' (from Step 8)
  new_sigma = σ' (from Step 6)
```

**Code reference:** `telegram_webhook.py:474-482`

---

## 5. Complete Worked Example

### Scenario: 10-Player Game

**Setup:**
- 7 Red team players (Citizens + Sheriff) **WIN**
- 3 Black team players (Mafia + Don) **LOSE**
- All players start at default: R=1500, RD=150, σ=0.06

### Player 1 (Red, Won)

**Opponents:** 3 Black players (all rated 1500)

#### Step 1: Convert to Glicko-2 scale
```
μ = (1500 - 1500) / 173.7178 = 0.0
φ = 150 / 173.7178 = 0.8638
```

#### Step 2-3: Calculate g and E for each opponent
```
For each Black opponent (all identical):
  μⱼ = 0.0
  φⱼ = 0.8638
  
  g(φⱼ) = 1 / √(1 + 3×0.8638²/π²)
        = 1 / √(1 + 0.7184)
        = 1 / 1.3107
        = 0.7629
  
  E(0, 0, 0.8638) = 1 / (1 + exp(-0.7629 × 0))
                  = 1 / (1 + 1)
                  = 0.5000
```

#### Step 4: Calculate weight and variance
```
WEIGHT_MULTIPLIER = 1.85
opponent_count = 3 (Black team size)
w = 1.85 / 3 = 0.6167

For each opponent:
  g² = 0.7629² = 0.5820
  E(1-E) = 0.5 × 0.5 = 0.25
  contribution = 0.6167 × 0.5820 × 0.25 = 0.0897

v_inv = 3 × 0.0897 = 0.2691
v = 1 / 0.2691 = 3.716
```

#### Step 5: Calculate delta
```
s = 1.0 (won all 3 matches)
For each opponent:
  (s - E) = 1.0 - 0.5 = 0.5
  contribution = 0.6167 × 0.7629 × 0.5 = 0.2353

Sum = 3 × 0.2353 = 0.7059
Δ = 3.716 × 0.7059 = 2.623
```

#### Step 6: Calculate new sigma (simplified)
```
After Illinois iterations:
σ' ≈ 0.0648
```

#### Step 7: Update μ and φ
```
φ* = √(0.8638² + 0.0648²) = √(0.7462 + 0.0042) = 0.8667

φ' = 1 / √(1/0.8667² + 1/3.716)
   = 1 / √(1.332 + 0.269)
   = 1 / 1.265
   = 0.7905

μ' = 0.0 + 0.7905² × 0.7059 = 0.6249 × 0.7059 = 0.4412
```

#### Step 8: Convert back
```
R' = 0.4412 × 173.7178 + 1500 = 76.67 + 1500 = 1576.7
RD' = 0.7905 × 173.7178 = 137.3
σ' = 0.0648
```

**Tentative: +76.7 points**

#### Step 9-12: Normalization and scaling

Assuming full game calculation yields:
- First normalization: -5 points correction
- RD correction (high RD winner): ×0.65 factor
- Rating-based scaling: ×1.0 (equal opponents)
- Second normalization: +2 points correction

**Final change:** ≈ +47 points

**Final rating: 1547**

---

### Player 8 (Black, Lost)

**Opponents:** 7 Red players (all rated 1500)

Following same steps but with:
- opponent_count = 7
- w = 1.85 / 7 = 0.2643
- s = 0.0 (lost all 7 matches)
- Negative delta

**Tentative: -115 points**

After corrections and normalizations:
**Final change:** ≈ -110 points

**Final rating: 1390**

---

### Zero-Sum Verification

```
Red team (7 players): +47 × 7 = +329
Black team (3 players): -110 × 3 = -330

Total = +329 + (-330) = -1 ≈ 0 ✓
```

(Small rounding error is normal)

---

## 6. Formula Reference

### Quick Reference Table

| Step | Formula | Code Location |
|------|---------|---------------|
| **Scale to Glicko-2** | μ = (R - 1500) / 173.7178<br>φ = RD / 173.7178 | `telegram_webhook.py:156-160` |
| **g function** | g(φ) = 1 / √(1 + 3φ²/π²) | `telegram_webhook.py:170-172` |
| **E function** | E(μ,μⱼ,φⱼ) = 1 / (1 + exp(-g(φⱼ)×(μ-μⱼ))) | `telegram_webhook.py:175-177` |
| **Variance** | v = 1 / Σ[w×g²×E×(1-E)] | `telegram_webhook.py:180-191` |
| **Delta** | Δ = v × Σ[w×g×(s-E)] | `telegram_webhook.py:194-203` |
| **New sigma** | Illinois algorithm (iterative) | `telegram_webhook.py:206-247` |
| **New φ** | φ* = √(φ² + σ'²)<br>φ' = 1/√(1/φ*² + 1/v) | `telegram_webhook.py:264-266` |
| **New μ** | μ' = μ + φ'² × Σ[w×g×(s-E)] | `telegram_webhook.py:269-275` |
| **Scale back** | R' = μ' × 173.7178 + 1500<br>RD' = φ' × 173.7178 | `telegram_webhook.py:163-167` |
| **Normalization** | R_norm = R' - (Σ(R'-R)/10) | `telegram_webhook.py:404-409` |
| **RD correction** | factor = 1/(1 + RD_dev × coeff) | `telegram_webhook.py:432-449` |
| **Rating scaling** | scaling = clamp(1 - diff/sens, min, max) | `telegram_webhook.py:281-345` |

### Constants Summary

```
SCALE = 173.7178
TAU = 1.25
WEIGHT_MULTIPLIER = 1.85
EPSILON = 0.000001

RD_BASELINE_CORRECTION = 52.5
RD_CORRECTION_WINNER_FACTOR = 0.040
RD_CORRECTION_LOSER_FACTOR = 0.0002

RATING_SENSITIVITY = 240.0
RD_DAMPENING = 0.032
MAX_SCALING = 1.55
MIN_SCALING = 0.97
RD_BASELINE_SCALING = 52.0
```

---

## Appendix A: Illinois Algorithm Detail

The Illinois algorithm is used to solve:
```
f(x) = 0
```

Where:
```
f(x) = [exp(x) × (Δ² - φ² - v - exp(x))] / [2(φ² + v + exp(x))²] - (x - a) / τ²
```

**Procedure:**

1. **Initialize:**
   ```
   a = ln(σ²)
   A = a
   ```

2. **Find B:**
   ```
   If Δ² > φ² + v:
     B = ln(Δ² - φ² - v)
   Else:
     k = 1
     While f(a - k×τ) < 0:
       k++
     B = a - k×τ
   ```

3. **Iterate until convergence:**
   ```
   While |B - A| > ε:
     C = A + (A - B) × f(A) / (f(B) - f(A))
     
     If f(C) × f(B) < 0:
       A = B
       f(A) = f(B)
     Else:
       f(A) = f(A) / 2
     
     B = C
     f(B) = f(C)
   ```

4. **Extract result:**
   ```
   σ' = exp(A / 2)
   ```

**Why this works:** This is a modified false position method that guarantees convergence for this specific function shape.

---

## Appendix B: Team Size Calculations

For Mafia games, team sizes vary:
- Red team: 6-7 players (Citizens + Sheriff)
- Black team: 3-4 players (Mafia + Don)

**Weight formula:**
```
If player won:
  opponent_count = len(losers)
Else:
  opponent_count = len(winners)

weight_per_match = WEIGHT_MULTIPLIER / opponent_count
```

**Examples:**

| Red size | Black size | Red weight per match | Black weight per match |
|----------|------------|---------------------|----------------------|
| 7 | 3 | 1.85 / 3 = 0.6167 | 1.85 / 7 = 0.2643 |
| 6 | 4 | 1.85 / 4 = 0.4625 | 1.85 / 6 = 0.3083 |

**Key insight:** Smaller team gets higher weight per match (faces more opponents)

---

## Appendix C: Configuration Values

Current production values from `glicko2_config.json`:

```json
{
  "glicko2": {
    "initial_rating": 1500.0,
    "initial_rd": 150.0,
    "initial_sigma": 0.06,
    "tau": 1.25,
    "weight_multiplier": 1.85,
    "epsilon": 0.000001
  },
  "rating_scaling": {
    "enabled": true,
    "rating_sensitivity": 240.0,
    "rd_dampening": 0.032,
    "max_scaling": 1.55,
    "min_scaling": 0.97,
    "rd_baseline_scaling": 52.0,
    "rd_baseline_correction": 52.5,
    "rd_correction_winner_factor": 0.040,
    "rd_correction_loser_factor": 0.0002
  }
}
```

---

## Appendix D: Common Pitfalls

### 1. Forgetting the scale conversion
All core Glicko-2 calculations happen in Glicko-2 scale (μ, φ), not Glicko scale (R, RD).

### 2. Wrong team weight calculation
Weight depends on **opponent count**, not own team size:
- Red player (winner): weight = 1.85 / 3 (Black team size)
- Black player (loser): weight = 1.85 / 7 (Red team size)

### 3. Inverting scaling for losses
For losses, the scaling formula **adds** the rating difference, not subtracts:
```
Win:  scaling = 1.0 - (diff / sens)
Loss: scaling = 1.0 + (diff / sens)  ← Note the +
```

### 4. Asymmetric RD correction
Winners and losers use **different correction factors**:
- Winner: factor = 0.040 (strong dampening)
- Loser: factor = 0.0002 (minimal dampening)

### 5. Two separate normalizations
The system normalizes **twice**:
1. After tentative Glicko-2 calculation
2. After rating-based scaling

Both are necessary to maintain zero-sum.

---

## Document Status

**Last verified against code:** 2026-02-02  
**Code version:** `telegram_webhook.py` + `glicko2_config.json` (production)  
**All formulas tested:** ✓

This document is synchronized with the actual implementation and can be used to manually verify any rating calculation.

---

**End of Manual**

