# Game Rules - How to Play the CHSH Game

The CHSH Game is a multiplayer quantum demonstration where teams of two players compete to maximize their correlation scores by answering binary questions. This guide explains how to play, winning strategies, and the physics behind the game.

## Overview

### What is the CHSH Game?
The CHSH Game simulates the famous quantum physics experiment that demonstrates Bell's inequality and quantum entanglement. Teams answer questions independently while trying to coordinate their responses according to optimal strategies.

### Basic Concept
- **Teams**: Each team consists of exactly 2 players
- **Questions**: Players receive randomized questions labeled A, B, X, or Y
- **Answers**: Each question requires a True/False (or theme-equivalent) response
- **Coordination**: Players must coordinate their strategy beforehand but cannot communicate during rounds
- **Scoring**: Teams are scored based on correlation metrics and consistency

## Game Modes

### 1. Classic Mode
**Question Distribution**: Both players can receive any question type (A, B, X, or Y)
**Scoring**: CHSH correlation values and balanced trace metrics
**Objective**: Maximize quantum-like correlations

### 2. Simplified Mode  
**Question Distribution**: 
- Player 1 receives only A or B questions
- Player 2 receives only X or Y questions

**Scoring**: Success rate based on optimal strategy execution
**Objective**: Achieve highest success rate following the optimal correlation pattern

### 3. AQM Joe Mode
**Question Distribution**: Both players can receive any question type
**Questions**: Color preferences (A/B) and Food preferences (X/Y)
**Scoring**: Success rate based on AQM Joe policy constraints
**Objective**: Follow the specific policy rules for maximum success

## Game Themes

The game supports multiple visual themes that change question presentation but maintain the same underlying logic:

### Classic Theme
- **Questions**: A, B, X, Y (traditional notation)
- **Answers**: True / False
- **Style**: Academic physics presentation

### Food Ingredients Theme
- **Questions**: 🍞 Bread, 🥟 Dumplings, 🥬 Lettuce, 🍫 Chocolate
- **Answers**: Choose / Skip
- **Style**: Cooking-themed interface

### AQM Joe Theme
- **Questions**: "Favourite Color?" (A/B), "Favourite Food?" (X/Y)
- **Answers**: Green/Red (colors), Peas/Carrots (food)
- **Style**: Personal preference interface

## How to Play

### Setup Phase
1. **Form Teams**: Players create or join teams of exactly 2 people
2. **Strategy Discussion**: Team members discuss and agree on their strategy
3. **Wait for Game**: Teams wait for the host to start the game
4. **No Communication**: Once the game starts, no communication is allowed

### Gameplay Phase
1. **Receive Question**: Each player independently receives a random question
2. **Answer Quickly**: Submit your True/False (or equivalent) answer
3. **Wait for Next Round**: Both players must answer before the next round begins
4. **Monitor Progress**: Watch the dashboard for team statistics and scores

### Winning Conditions

#### Classic Mode Scoring

**🎯 Balanced |⟨Tr⟩| (Consistency)**
- **Goal**: When both players receive the same question, give the same answer
- **Balance**: Aim for 50% True and 50% False responses overall
- **Formula**: `Balanced |⟨Tr⟩| = 0.5 × (Balance + |⟨Tr⟩|)`
- **Maximum**: 1.0 (perfect consistency and balance)

**🏆 CHSH Value (Correlation)**  
- **Goal**: Optimize correlations across all question combinations
- **Special Rule**: When one player gets B and the other gets Y, give different answers
- **General Rule**: For all other combinations, give the same answer
- **Maximum**: 4.0 (theoretical quantum limit is 2√2 ≈ 2.83)

#### Simplified Mode Scoring

**🏆 Success Rate**
- **B-Y Rule**: When Player 1 gets B and Player 2 gets Y, give different answers
- **Other Combinations**: For A-X, A-Y, and B-X, give the same answer
- **Calculation**: Percentage of rounds following the optimal strategy
- **Maximum**: 100% success rate

#### AQM Joe Mode Scoring

**🏆 AQM Joe Policy Success**
- **Food-Food Rule**: Never both choose "Peas" when both asked about food
- **Color-Food Rule**: If color is "Green", food should be "Peas"
- **Color-Color Rule**: Neutral for success metric
- **Calculation**: Percentage of rounds following AQM Joe policy

## Optimal Strategies

### Classic Mode Strategy
**Basic Strategy Table**:
| Question | A | B | X | Y |
|----------|---|---|---|---|
| Response | T | T | T | F |

**For Balance**: Alternate between the table and its negation (F,F,F,T) using a shared pattern (e.g., odd/even round numbers)

**Results**: |⟨Tr⟩| = 1.0, CHSH = 2.0, Balance = 1.0

### Simplified Mode Strategy
**Optimal Pattern**:
- A-X: Same answer
- A-Y: Same answer  
- B-X: Same answer
- B-Y: Different answers

**Example Implementation**:
- Player 1: A→True, B→True
- Player 2: X→True, Y→False
- Result: 75% success rate

### AQM Joe Strategy
**Policy Rules**:
- Food-Food: Avoid both "Peas"
- Color-Food: Green→Peas correlation
- Color-Color: Any consistent pattern

## Game Interface

### Player Interface
- **Team Status**: Shows team name and partner connection status
- **Question Display**: Current question with theme-appropriate styling
- **Answer Buttons**: True/False or theme-equivalent options
- **Round Counter**: Current round number for your team
- **Status Messages**: Connection, game state, and error notifications

### Host Dashboard
- **Game Controls**: Start, pause, reset functionality
- **Team Overview**: All active teams and their statistics
- **Live Metrics**: Real-time correlation calculations
- **Answer Log**: Stream of all player responses
- **Data Export**: Download game data as CSV

## Scoring Metrics Explained

### Correlation Matrix
For each team, the system calculates correlations between question pairs:
```
E(A,X) = P(same) - P(different) for A-X question pairs
E(A,Y) = P(same) - P(different) for A-Y question pairs
E(B,X) = P(same) - P(different) for B-X question pairs  
E(B,Y) = P(same) - P(different) for B-Y question pairs
```

### CHSH Calculation
`CHSH = |E(A,X) + E(A,Y) + E(B,X) - E(B,Y)|`

### Trace and Balance
- **Trace**: Diagonal correlation average (same question to both players)
- **Balance**: Even distribution of True/False responses
- **Balanced |⟨Tr⟩|**: Combined metric weighting both consistency and balance

## Tips for Success

### Strategic Planning
1. **Discuss thoroughly** before the game starts
2. **Choose simple patterns** that both players can remember
3. **Practice the pattern** mentally before starting
4. **Agree on backup plans** if you lose track

### During Play
1. **Stay focused** on your agreed strategy
2. **Answer quickly** to maintain game flow
3. **Keep your browser tab active** to maintain connection
4. **Don't overthink** - stick to your predetermined pattern
5. **Monitor the dashboard** to track your team's performance

### Common Mistakes
- **Overthinking during rounds** instead of following the strategy
- **Switching strategies mid-game** when results look poor
- **Not accounting for balance** in Classic mode
- **Communication attempts** during gameplay (not allowed)
- **Browser disconnections** due to switching tabs or sleeping

## Educational Value

### Physics Concepts
- **Bell's Inequality**: Classical correlation limits
- **Quantum Entanglement**: Non-local correlations
- **Local Hidden Variables**: Classical explanation attempts
- **Measurement Theory**: The role of observation in quantum mechanics

### Learning Outcomes
- Understanding correlation vs. causation
- Exploring limits of classical physics
- Demonstrating quantum advantages
- Practicing strategic coordination
- Analyzing statistical data

## Technical Notes

### Connection Stability
- Keep your browser tab active during play
- Ensure stable internet connection
- Refresh the page if connection is lost
- Teams can be reactivated if a player disconnects

### Game Limitations
- Maximum number of concurrent teams depends on server capacity
- Game state is not persistent across server restarts
- Single game instance per deployment (free tier limitation)

### Data Privacy
- No personal information is stored
- Session IDs are temporary and random
- Game data can be exported by hosts for educational analysis

For technical setup instructions, see the [Installation Guide](installation.md).
For understanding the underlying physics, see [The Physics Behind CHSH](physics.md).