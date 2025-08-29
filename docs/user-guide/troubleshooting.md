# Troubleshooting

This guide helps resolve common issues when playing or hosting the CHSH Game.

## Connection Issues

### "Cannot connect to server" or Connection Lost

**Symptoms**: 
- Page won't load
- "Disconnected" status in the interface
- No real-time updates

**Solutions**:
1. **Check your internet connection**
   - Try loading other websites
   - Reset your WiFi/network connection
   - Switch to a different network if available

2. **Refresh the page**
   - Press `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac) for a hard refresh
   - This clears cache and reloads all resources

3. **Try a different browser**
   - Test with Chrome, Firefox, Safari, or Edge
   - Ensure JavaScript is enabled
   - Disable browser extensions that might block WebSockets

4. **Check server status**
   - If using the hosted version, the server might be temporarily down
   - Try the alternate URL if provided
   - Contact the host/administrator

### WebSocket Connection Failures

**Symptoms**:
- Game loads but real-time features don't work
- Questions don't appear
- Dashboard doesn't update

**Solutions**:
1. **Check firewall/proxy settings**
   - Corporate networks may block WebSocket connections
   - Contact your IT administrator
   - Try using a personal network/mobile hotspot

2. **Browser settings**
   - Ensure WebSockets are enabled (default in modern browsers)
   - Clear browser cache and cookies
   - Disable VPN if using one

## Team Management Issues

### Cannot Join Team

**Issue**: "Team is full" or "Cannot join team"

**Solutions**:
- Teams are limited to 2 players maximum
- Choose a different team from the available list
- Create a new team instead
- Wait for a spot to become available

### Partner Disconnected

**Issue**: Your partner left or disconnected during the game

**Solutions**:
- **For remaining player**: You can continue playing solo (though statistics may be affected)
- **For new players**: You can join the team to reactivate it
- **For hosts**: Monitor team status and help reform teams as needed

### Team Not Showing as "Ready"

**Issue**: Team doesn't appear in the paired teams list

**Causes & Solutions**:
- **Need exactly 2 players**: Add a second player to the team
- **Both players must be connected**: Check that both team members are online
- **Server synchronization**: Wait a few seconds for status to update

## Gameplay Issues

### Questions Not Appearing

**Issue**: Waiting for questions but none appear

**Troubleshooting**:
1. **Game not started**: Only hosts can start the game from the dashboard
2. **Team not paired**: Ensure your team has exactly 2 players
3. **Connection issue**: Check your network connection
4. **Browser tab inactive**: Keep the game tab active and focused

### Answers Not Being Recorded

**Issue**: Clicking True/False but responses aren't registered

**Solutions**:
1. **Connection check**: Verify you're still connected to the server
2. **Wait for question**: Ensure a question is currently displayed
3. **Single click**: Don't double-click the answer buttons
4. **Browser refresh**: Reload the page and rejoin your team

### Statistics Not Updating

**Issue**: Dashboard statistics seem frozen or incorrect

**Solutions**:
1. **Refresh dashboard**: Reload the dashboard page
2. **Check answer count**: Ensure teams are actually playing
3. **Clear browser cache**: Force reload with `Ctrl+F5`
4. **Wait for updates**: Statistics update after each answer submission

## Dashboard/Host Issues

### Cannot Start Game

**Issue**: "Start Game" button doesn't work or no teams respond

**Troubleshooting**:
1. **Check paired teams**: Ensure at least one team has 2 players
2. **Browser console**: Check for JavaScript errors (F12 → Console)
3. **Refresh dashboard**: Reload the dashboard page
4. **Server restart**: Contact administrator for server restart if needed

### Dashboard Not Displaying Teams

**Issue**: Team count shows 0 or teams aren't listed

**Solutions**:
1. **Player connection**: Verify players are actually connected
2. **Database sync**: Teams might need time to synchronize
3. **Page refresh**: Reload the dashboard
4. **Clear cache**: Clear browser cache and reload

### CSV Download Not Working

**Issue**: "Download CSV" produces empty file or error

**Solutions**:
1. **Play some rounds**: Ensure there's data to download (answers recorded)
2. **Browser compatibility**: Try a different browser
3. **Pop-up blocker**: Check if downloads are being blocked
4. **File permissions**: Ensure you have permission to download files

## Performance Issues

### Slow Response Times

**Issue**: Game feels laggy or unresponsive

**Solutions**:
1. **Close other tabs**: Free up browser memory
2. **Check CPU usage**: Close other applications
3. **Network optimization**: 
   - Use wired connection if possible
   - Move closer to WiFi router
   - Close bandwidth-heavy applications

### Browser Crashes or Freezes

**Issue**: Browser becomes unresponsive during gameplay

**Solutions**:
1. **Update browser**: Ensure you're using the latest version
2. **Clear cache**: Clear browser cache and data
3. **Disable extensions**: Temporarily disable browser extensions
4. **Restart browser**: Close and reopen your browser
5. **Try different browser**: Test with a different browser

## Error Messages

### "Session expired" or "Invalid session"

**Solutions**:
- Refresh the page to get a new session
- Clear browser cookies and cache
- Try an incognito/private browsing window

### "Database error" or "Server error"

**Solutions**:
- These are server-side issues
- Try refreshing the page
- Contact the host/administrator
- Wait a few minutes and try again

### "Maximum players reached"

**Solutions**:
- The server has a maximum capacity
- Wait for other players to leave
- Contact the host to increase capacity if possible

## Getting Additional Help

### For Players
1. Ask your instructor/host for assistance
2. Check with other players if they're experiencing similar issues
3. Try the solutions in this guide systematically

### For Hosts/Instructors
1. Check the [Developer Guide](../developer-guide/) for technical details
2. Review server logs for error messages
3. Contact technical support if available
4. Consider restarting the game/server if issues persist

### Reporting Issues
When reporting problems, include:
- **Browser type and version**
- **Operating system**
- **Exact error messages**
- **Steps to reproduce the issue**
- **Screenshots if applicable**

## Prevention Tips

### For Best Experience
1. **Use recommended browsers**: Chrome, Firefox, Safari, Edge (latest versions)
2. **Stable connection**: Use reliable internet connection
3. **Keep tabs minimal**: Close unnecessary browser tabs
4. **Stay updated**: Keep your browser updated
5. **Plan ahead**: Discuss strategy before game starts (no communication during play!)

### For Hosts
1. **Test beforehand**: Run a test session before the actual game
2. **Monitor actively**: Keep an eye on the dashboard during play
3. **Have backup plan**: Know how to restart/reset if needed
4. **Communicate clearly**: Ensure players understand the rules and technical requirements

---

Still having issues? Check the [Developer Guide](../developer-guide/) for more technical troubleshooting or contact your system administrator.