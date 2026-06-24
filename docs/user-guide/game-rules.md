# Game Rules & Strategy

## How to Play

The CHSH Game requires **at least two players** (one team of two), but it's more fun with multiple teams competing.

### Basic Game Flow

1. **Team Formation**
   - Players create or join teams of exactly 2 people
   - Teams can be reactivated if a previous team member leaves

2. **Question Assignment**
   - Each round, both players receive randomly selected questions: **A**, **B**, **X**, or **Y**
   - Each player gets their own question independently
   - Questions are assigned to create all possible combinations over time

3. **Response Phase**
   - Players respond with either **True** or **False**
   - Responses are based on a shared strategy agreed upon before the game starts
   - **⚠️ No communication is allowed during the game!**

4. **Continuous Rounds**
   - The game continues with new question rounds
   - Teams accumulate statistics over multiple rounds

## Winning Strategies

### Strategy 1: Best Balanced |⟨Tr⟩| 🎯

**Goal**: Maximize the balanced trace average metric.

**Rules**:
- When you and your partner receive the **same question** (A/A, B/B, X/X, or Y/Y):
  - Both answer the **same** (both True or both False)
  - Answer True/False about **50% of the time** for each question type
- For **different question pairs**, see "Best CHSH" strategy below

**Scoring**:
- **Trace/4 = ⟨Tr⟩**: ±1 if partners always agree, 0 if they always disagree
- **Balance**: 1 if True/False responses are 50:50 for each question, 0 if always one answer
- **Balanced |⟨Tr⟩|**: 0.5 × (balance + |⟨Tr⟩|) - higher is better

### Strategy 2: Best CHSH 🏆

**Goal**: Maximize the CHSH value to demonstrate quantum-like correlations.

**Rules**:
- **Special case**: When one player gets **B** and the other gets **Y**:
  - Answer **differently** (one True, one False)
- **All other question pairs**: Answer the **same** (both True or both False)

**The Question Pairs**:
- **Same answers**: AA, AB, AX, AY, BA, BB, BX, XA, XB, XX, XY, YA, YX, YY
- **Different answers**: BY, YB

## Advanced Strategy Tips

### Pre-Game Planning
1. **Decide on your strategy** before the game starts
2. **Agree on conventions**:
   - How to handle A vs B questions?
   - How to handle X vs Y questions?
   - What's your "default" answer for each question type?

### Example Strategy Framework
```
Question A: Always answer True
Question B: Always answer False  
Question X: Answer True 50% of time (use round number: odd=True, even=False)
Question Y: Answer False 50% of time (opposite of X)

Special rule: If partner has Y and you have B (or vice versa), 
flip your normal answer.
```

### Monitoring Your Performance
- Watch the dashboard statistics to see how well your strategy is working
- **Trace Average**: Shows how often you and your partner agree
- **Balance**: Shows how evenly distributed your answers are
- **CHSH Value**: Shows how well you're demonstrating quantum-like correlations

## The Physics Behind the Game

### CHSH Inequality
The CHSH game is based on a real quantum physics experiment that demonstrates "quantum entanglement" - a phenomenon where particles can be correlated in ways that seem impossible according to classical physics.

### Classical vs Quantum Limits
- **Classical limit**: CHSH values ≤ 2
- **Quantum maximum**: CHSH values ≤ 2√2 ≈ 2.828
- **Your goal**: Try to exceed the classical limit of 2!

### Why This Matters
When teams consistently achieve CHSH values above 2, they're demonstrating correlations that would be impossible for classical objects. This is one of the most famous demonstrations of quantum mechanics in action.

## Tips for Success

1. **Communication is key** - Plan your strategy thoroughly before starting
2. **Stay consistent** - Stick to your agreed strategy throughout the game
3. **Practice makes perfect** - Try different strategies across multiple games
4. **Monitor the dashboard** - Learn from your statistics to improve
5. **Have fun** - You're exploring one of the deepest mysteries in physics!

---

Ready to start playing? Check out the [Getting Started Guide](./getting-started.md) for detailed setup instructions.