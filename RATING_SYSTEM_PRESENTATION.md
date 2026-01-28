# Glicko-2 Rating System for Mafia
## A Modern Approach to Player Skill Assessment

---

## The Problem with Win Percentage

**Before:**
- Player A: 60% win rate (60 wins, 40 losses) against rookies
- Player B: 55% win rate (55 wins, 45 losses) against pros

**Who's better?** 🤔

Traditional win percentage treats all opponents equally - beating a beginner = beating a champion.

**We need a smarter system!**

---

## Enter Glicko-2

**What is it?**
- Advanced rating system developed by Mark Glickman (Harvard)
- Used in online chess (Lichess, Chess.com), competitive gaming
- Evolution of Elo rating with added precision

**Why not plain Elo?**
- Elo: Just one number (rating)
- Glicko-2: Three numbers working together for accuracy

---

## The Three Magic Numbers

### 1. **Rating** (R)
- **Starts at:** 1500
- **What it means:** Your skill level
- **Range:** Typically 1000-2000 (no hard limits)

**Example:**
- Beginner: ~1200-1400
- Average: ~1450-1550
- Strong player: ~1600-1700
- Expert: ~1800+

---

## The Three Magic Numbers

### 2. **Rating Deviation (RD)**
- **Starts at:** 350
- **What it means:** Uncertainty about your true skill
- **Range:** 350 (new player) → ~60-100 (established player)

**Think of it as:**
- High RD (300+): "We're not sure how good you are yet"
- Low RD (60-80): "We're confident about your skill level"

**Why it matters:**
- New players' ratings change faster (big RD)
- Veterans' ratings change slower (small RD)

---

## The Three Magic Numbers

### 3. **Volatility (σ - sigma)**
- **Starts at:** 0.06
- **What it means:** How consistent your performance is
- **Range:** 0.03-0.12 (lower = more consistent)

**Think of it as:**
- Low sigma: Stable player (performs at their level consistently)
- High sigma: Streaky player (varies between brilliant and terrible)

**Example:**
- σ = 0.04: You play at 1600 ± small variation
- σ = 0.10: You play anywhere from 1400 to 1800

---

## How It Works: The Big Picture

**After each game:**

1. **Look at opponents**
   - Who did you play against?
   - What were their ratings?
   - How certain are we about their ratings (RD)?

2. **Compare expected vs actual**
   - Expected: "Based on ratings, you should win/lose"
   - Actual: "But here's what really happened"

3. **Update all three numbers**
   - Rating changes based on surprise factor
   - RD gets smaller (we're more certain now)
   - Sigma adjusts if you performed unexpectedly

---

## Example 1: Beating Expectations

**Player:** Міша (Rating 1500, RD 200)
**Opponent:** Legendary player (Rating 1800, RD 80)

**Expected outcome:** Міша should lose (20% win chance)

**Actual outcome:** Міша WINS! 🎉

**Rating change:**
- Міша: 1500 → **1650** (+150)
  - Big jump because he beat a strong opponent
  - System says: "Wow, maybe he's better than we thought!"

---

## Example 2: Meeting Expectations

**Player:** Аня (Rating 1600, RD 100)
**Opponent:** Weak player (Rating 1300, RD 150)

**Expected outcome:** Аня should win (85% chance)

**Actual outcome:** Аня wins ✓

**Rating change:**
- Аня: 1600 → **1608** (+8)
  - Small change because she did what was expected
  - RD drops: 100 → 92 (system is more confident)

---

## Example 3: Disappointing Performance

**Player:** Pётр (Rating 1700, RD 75)
**Opponent:** Beginner (Rating 1250, RD 300)

**Expected outcome:** Pётр should win (95% chance)

**Actual outcome:** Pётр LOSES! 😱

**Rating change:**
- Pётр: 1700 → **1580** (-120)
  - Big drop because he lost to a much weaker player
  - Sigma increases: 0.05 → 0.08 (inconsistent performance)

---

## Our Custom Implementation: Mafia Specifics

**Challenge:** Mafia is a 10-player team game!
- Not 1v1 like chess
- Citizens (6) + Sheriff (1) vs Mafia (3 including Don)

**Our Solution:** 45 mini-games per game
- Each player plays against all 9 others
- 10 players = 45 pairwise comparisons

**Scoring:**
- **Win against opponent:** 1.0 point
- **Loss against opponent:** 0.0 points
- **Same team (both win/lose):** 0.5 points (draw)

---

## Example: One Game Breakdown

**Game:** Citizens win
**Player:** Сяргей (Citizen, won)

**His opponents:**
- 6 teammates (also won): 6 × 0.5 = 3.0 points
- 3 mafia (lost): 3 × 1.0 = 3.0 points
- **Total: 6.0 points out of 9 possible**

**If Сяргей was Mafia (lost):**
- 2 teammates (also lost): 2 × 0.5 = 1.0 points
- 7 citizens (won): 7 × 0.0 = 0.0 points
- **Total: 1.0 points out of 9 possible**

---

## Why This Works

**1. Opponent strength matters**
```
Beating 5 strong players (1800 rating) > Beating 5 weak players (1200 rating)
```

**2. Uncertainty is honest**
```
New player with 3 games: ±300 RD
Veteran with 100 games: ±70 RD
```

**3. Consistency is tracked**
```
Stable player: Small rating swings
Streaky player: Bigger rating swings (system adapts)
```

**4. Fair to everyone**
```
Rookies gain/lose points faster (helps them find their level)
Veterans gain/lose points slower (their rating is established)
```

---

## Strengths ✅

### 1. **Opponent Quality Matters**
- Beating a 1800 player >> Beating a 1200 player
- Losing to 1800 is less painful than losing to 1200

### 2. **Self-Balancing**
- New players find their level quickly (10-20 games)
- Established players have stable ratings
- No need for manual "resets" or "seasons"

### 3. **Uncertainty is Built-In**
- RD shows "confidence interval"
- Rating 1500 ± 200 = anywhere from 1300-1700
- Rating 1500 ± 60 = probably 1440-1560

---

## Strengths ✅

### 4. **Detects Consistency**
- Sigma reveals if a player is stable or streaky
- Helps predict future performance

### 5. **Scientific & Battle-Tested**
- Used by major platforms (Chess.com, Lichess)
- Proven over millions of games
- Academically validated

---

## Weaknesses ⚠️

### 1. **Needs Time to Stabilize**
- First 10 games: Ratings swing wildly
- Need ~20-30 games for accurate rating
- **Our fix:** Show chart only after 10 games

### 2. **Team Game Complexity**
- In Mafia, you can't control your teammates
- Good player + bad team = loss = rating drop
- **Partially addressed:** All 9 opponents counted separately

### 3. **Role Imbalance Not Considered**
- Being Sheriff vs Citizen vs Mafia - all treated same
- No separate ratings per role
- **Trade-off:** Simpler system, overall skill assessment

---

## Weaknesses ⚠️

### 4. **Smurfing / New Accounts**
- Experienced player creates new account
- Starts at 1500, crushes beginners
- Takes ~10 games to reach true rating
- **Mitigation:** Small community, known players

### 5. **Inactive Players**
- RD increases over time with inactivity
- Player returns after 6 months → RD is high again
- **Trade-off:** Actually correct (skill may have changed)

---

## Key Parameters in Our System

| Parameter | Value | Meaning |
|-----------|-------|---------|
| **Initial Rating** | 1500 | Starting point for all players |
| **Initial RD** | 350 | Maximum uncertainty (brand new) |
| **Initial Sigma** | 0.06 | Moderate volatility assumption |
| **Tau (τ)** | 0.5 | How fast sigma can change |

**Tau = 0.5** means:
- Moderate system
- Sigma adjusts gradually, not drastically
- Balanced between stability and responsiveness

---

## Real Data Example: Player Evolution

**Ася (70 games):**

| Game # | Rating | RD | What Happened |
|--------|--------|-----|---------------|
| 1 | 1500 | 350 | Starting point |
| 5 | 1620 | 220 | Won 4 of 5, rating rising |
| 10 | 1580 | 180 | Lost a few, leveling off |
| 30 | 1650 | 95 | Consistent strong play |
| 70 | 1690 | 72 | Established expert |

**Interpretation:**
- True skill ~1650-1700 (proven over 70 games)
- Very consistent (low RD = 72)
- Upward trajectory = improving player

---

## When Ratings Look "Wrong"

**"Player X has 65% win rate but rating 1450?"**
- Probably played many games against weak opponents
- System correctly values opponent strength

**"Player Y has 50% win rate but rating 1700?"**
- Played many games against strong opponents
- Going 50-50 with experts means you're an expert!

**"Player Z's rating dropped after winning?"**
- Won but against much weaker expected opponents
- Example: 1800 player barely beats 1300 player
- System expected dominant win, not close game

---

## Comparison to Other Systems

| System | Pros | Cons |
|--------|------|------|
| **Win %** | Simple, easy to understand | Ignores opponent strength |
| **Elo** | Standard, widely known | No uncertainty measure, slower convergence |
| **Glicko-2** | Accurate, self-balancing, tracks uncertainty | Complex, needs time to stabilize |
| **TrueSkill** | Great for teams | Very complex, Microsoft patent |

**Our choice: Glicko-2** ✓
- Best balance of accuracy and complexity
- Open source, no patents
- Proven track record

---

## How to Read Your Rating

### Rating Number
- **1200-1400:** Learning the game
- **1400-1550:** Solid player, knows fundamentals
- **1550-1700:** Strong player, competitive
- **1700+:** Expert, top tier

### Rating Deviation (RD)
- **300+:** Very uncertain (< 5 games)
- **150-250:** Getting clearer (5-15 games)
- **100-150:** Fairly certain (15-30 games)
- **60-100:** Very certain (30+ games)

### The Chart
- **Upward trend:** Improving player
- **Flat line:** Found your level
- **Downward trend:** Slump or overrated initially

---

## Common Questions

**Q: Why does my rating go down when I win?**
A: Very rare, but happens if you barely beat much weaker opponents. System expected easy win.

**Q: Why do new players' ratings change so much?**
A: High RD (uncertainty) → bigger swings. After ~20 games, it stabilizes.

**Q: Is 1500 average?**
A: No! 1500 is starting point. Average depends on the player pool.

**Q: Can I game the system?**
A: Not really. Avoiding strong opponents? You'll have a high rating but large RD (everyone knows you're untested).

---

## Future Improvements

**Possible additions:**
1. **Role-specific ratings**
   - Separate ratings for Citizen, Mafia, Sheriff, Don
   - More complex but more detailed

2. **Decay for inactive players**
   - RD increases automatically after inactivity
   - Reflects uncertainty about current skill

3. **Team composition factor**
   - Weight losses less if paired with many weak teammates
   - Complex to implement fairly

4. **Confidence intervals on display**
   - Show "Rating: 1650 ± 85" on main table
   - More honest representation

---

## Summary

**What we have:**
- ✅ Glicko-2 rating system
- ✅ Accounts for opponent strength
- ✅ Tracks uncertainty (RD) and consistency (sigma)
- ✅ Custom implementation for 10-player team games
- ✅ Automatic balancing (no manual adjustments needed)

**What it gives us:**
- 📊 Fair skill assessment
- 🎯 Better matchmaking insight
- 📈 Player progression tracking
- 🏆 Meaningful competition

**Bottom line:**
*Much better than win percentage, worth the complexity!*

---

## Technical Details (For the Curious)

**Formula (simplified):**
```
New Rating = Old Rating + (RD factor) × (Actual - Expected)
```

Where:
- **RD factor:** Larger when uncertain (high RD)
- **Actual:** 1.0 (win), 0.5 (draw), 0.0 (loss)
- **Expected:** Calculated from rating difference and RD

**Full algorithm:** 
- ~150 lines of Python code
- Paper: http://www.glicko.net/glicko/glicko2.pdf
- Implementation: Based on official specification

---

## Questions?

**Want to dig deeper?**
- Original paper: glicko.net/glicko/glicko2.pdf
- Our implementation: `api/telegram_webhook.py` (Glicko-2 section)
- Test cases: `test_glicko2.py`

**Discussion points:**
- Should we add role-specific ratings?
- What about decay for inactive players?
- Other improvements?

---

# Thank You!

**Remember:**
- Rating ≈ skill level (1500 starting point)
- RD = uncertainty (lower is better)
- Sigma = consistency (lower is more stable)

**The system is fair, transparent, and battle-tested.**

*Now go play and improve your rating!* 🎮🏆

