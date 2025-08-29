# Getting Started

This guide will help you get up and running with the CHSH Game quickly.

## For Players

### Step 1: Access the Game
- **Live Game**: [chsh-game.fly.dev](https://chsh-game.fly.dev) or [chsh-game.onrender.com](https://chsh-game.onrender.com)
- **Local Setup**: See the [Developer Setup Guide](../developer-guide/setup.md) if running locally

### Step 2: Create or Join a Team
1. **Enter your name** in the player name field (optional but recommended)
2. **Create a new team**:
   - Enter a unique team name
   - Click "Create Team"
   - Wait for a partner to join
3. **Join an existing team**:
   - Select a team from the "Available Teams" list
   - Click "Join Team"
   - If the team has 2 players, you'll reactivate it

### Step 3: Plan Your Strategy
**⚠️ Important**: Discuss your strategy with your partner before the game starts! No communication is allowed during gameplay.

**Quick Strategy Options**:
- **Beginner**: Always answer the same as your partner - both say "True" or both say "False"
- **Advanced**: Use the CHSH optimal strategy (see [Game Rules](./game-rules.md))
- **Custom**: Develop your own strategy based on the game rules

### Step 4: Wait for Game Start
- The instructor/host will start the game from the dashboard
- You'll see a "Waiting for game to start..." message
- Once started, questions will appear automatically

### Step 5: Play the Game
1. **Receive your question**: You'll see A, B, X, or Y
2. **Answer quickly**: Click "True" or "False" based on your strategy
3. **Wait for next round**: After both players answer, a new round begins
4. **Continue playing**: The game runs continuously until the host pauses/stops

### Step 6: Monitor Your Performance
- Check the dashboard (if accessible) to see your team's statistics
- Watch for metrics like CHSH value, trace average, and balance
- Learn from your results to improve your strategy

## For Instructors/Hosts

### Step 1: Access the Dashboard
- Navigate to the dashboard: `/dashboard` (e.g., `localhost:8080/dashboard`)
- The dashboard provides game control and real-time monitoring

### Step 2: Monitor Team Formation
- Watch the "Active Teams" and "Connected Players" counters
- See team status: "Waiting for pair", "Active", or "Inactive"
- Teams need exactly 2 players to participate

### Step 3: Start the Game
1. **Ensure teams are ready**: Check that teams have 2 players each
2. **Click "Start Game"**: This begins question rounds for all paired teams
3. **Monitor progress**: Watch the statistics update in real-time

### Step 4: Manage the Game
- **Pause/Resume**: Use the pause button to temporarily stop the game
- **Reset Statistics**: Clear current data to start fresh
- **View Live Answers**: Toggle the answer log to see real-time responses
- **Download Data**: Export game results as CSV for analysis

### Step 5: Analyze Results
- Monitor key metrics:
  - **Trace Average**: How often teammates agree
  - **Balance**: How evenly distributed answers are
  - **CHSH Value**: Quantum correlation measurement
- Use the data to discuss quantum physics concepts with players

## Quick Troubleshooting

### Common Issues

**"Can't connect to server"**
- Check your internet connection
- Refresh the page
- Try a different browser

**"Team is full"**
- Teams are limited to 2 players
- Join a different team or create a new one
- Wait for a spot to open up

**"Game not starting"**
- Only the host can start the game from the dashboard
- Ensure your team has exactly 2 players
- Check that you're on the correct game instance

**"Questions not appearing"**
- Make sure the game has been started by the host
- Check your internet connection
- Refresh the page if needed

**"Partner disconnected"**
- The remaining player can continue or wait for reconnection
- New players can join to reactivate the team
- Teams can be reformed as needed

### Browser Compatibility
- **Recommended**: Chrome, Firefox, Safari, Edge (latest versions)
- **Required**: JavaScript enabled
- **Required**: WebSocket support (available in all modern browsers)

### Performance Tips
- Use a stable internet connection
- Close unnecessary browser tabs
- Keep the game tab active for best performance

## Next Steps

- **Learn the rules**: Read the [Game Rules & Strategy](./game-rules.md) guide
- **Get help**: Check the [Troubleshooting](./troubleshooting.md) section
- **Technical setup**: See the [Developer Guide](../developer-guide/) for local installation

Ready to explore quantum physics through gameplay? Have fun!