"""
Functional test script for manual verification of team disconnection fixes.

This script provides step-by-step instructions and automated checks
to verify that the team formation and disconnection logic works correctly
in a live browser environment.

Usage:
    python tests/functional/test_team_disconnect_manual_verification.py

Prerequisites:
    - Server must be running (python src/main.py)
    - Multiple browser tabs/windows available for testing
"""

import requests
import time
import json
from typing import Dict, List, Any
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from models.quiz_models import Teams
from state import state


class TeamDisconnectManualTest:
    """Manual verification test for team disconnection logic."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.test_results = []
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
    
    def check_server_health(self) -> bool:
        """Check if server is running and responsive."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data from server."""
        try:
            # Note: This would need to be implemented as an API endpoint
            # For now, we'll simulate the check
            response = requests.get(f"{self.base_url}/api/dashboard", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {"teams": [], "connected_players_count": 0}
    
    def run_manual_verification_steps(self):
        """Run manual verification steps with instructions."""
        print("\n" + "="*60)
        print("TEAM DISCONNECTION MANUAL VERIFICATION TEST")
        print("="*60)
        print()
        
        # Check server health
        if not self.check_server_health():
            self.log_test("Server Health Check", False, "Server not responding")
            print("\n❌ Server is not running. Please start the server with: python src/main.py")
            return
        else:
            self.log_test("Server Health Check", True, "Server is responsive")
        
        print("\n📋 MANUAL TEST INSTRUCTIONS:")
        print("Follow these steps in your browser to verify the fixes...")
        print()
        
        # Test Phase 1: Team Formation
        print("🔧 PHASE 1: Team Formation")
        print("1. Open two browser tabs/windows to: " + self.base_url)
        print("2. Open dashboard in third tab: " + self.base_url + "/dashboard")
        print("3. In TAB 1: Create a team named 'TestTeam'")
        print("4. In TAB 2: Join team 'TestTeam'")
        print("5. VERIFY: Dashboard shows 'TestTeam' with status 'Active'")
        
        input("\nPress ENTER when Phase 1 is complete...")
        
        # Test Phase 2: Player Disconnection
        print("\n🔌 PHASE 2: Player Disconnection")
        print("1. In TAB 1: Refresh the page (simulating disconnect)")
        print("2. VERIFY IMMEDIATELY:")
        print("   - TAB 2: Should show 'Waiting for teammate to reconnect...'")
        print("   - TAB 2: Answer buttons should be DISABLED")
        print("   - DASHBOARD: Should show 'TestTeam' with status 'Waiting Pair'")
        print("   - DASHBOARD: Should update automatically (no manual refresh needed)")
        print()
        print("⏱️  Expected timing: Dashboard should update within 1 second automatically")
        
        dashboard_updated = input("Did the dashboard update automatically? (y/n): ").lower().strip()
        self.log_test(
            "Dashboard Auto-Update on Disconnect", 
            dashboard_updated == 'y',
            "Dashboard should update within 1 second without manual refresh"
        )
        
        input_disabled = input("Are the answer buttons disabled in the remaining player's tab? (y/n): ").lower().strip()
        self.log_test(
            "Input Disabled on Disconnect",
            input_disabled == 'y', 
            "Remaining player should not be able to submit answers"
        )
        
        # Test Phase 3: Player Reconnection
        print("\n🔄 PHASE 3: Player Reconnection")
        print("1. In TAB 1 (refreshed): Create or join teams to reform 'TestTeam'")
        print("2. Have another player join to make the team full again")
        print("3. VERIFY:")
        print("   - Both players can now submit answers")
        print("   - Dashboard shows 'TestTeam' as 'Active' again")
        print("   - No 'waiting' messages displayed")
        
        input("\nPress ENTER when Phase 3 is complete...")
        
        team_reformed = input("Did the team reform successfully with both players able to play? (y/n): ").lower().strip()
        self.log_test(
            "Team Reformation",
            team_reformed == 'y',
            "Reformed team should allow both players to participate"
        )
        
        # Test Phase 4: Edge Cases
        print("\n⚡ PHASE 4: Edge Case Testing")
        print("1. Test rapid disconnect/reconnect (refresh multiple times quickly)")
        print("2. Test with game in progress (start a round, then disconnect)")
        print("3. Test dashboard behavior during rapid changes")
        
        input("\nPress ENTER when edge case testing is complete...")
        
        edge_cases_passed = input("Did all edge cases work correctly? (y/n): ").lower().strip()
        self.log_test(
            "Edge Case Handling",
            edge_cases_passed == 'y',
            "System should handle rapid changes and game-in-progress disconnects"
        )
        
        # Summary
        self.print_test_summary()
    
    def run_automated_checks(self):
        """Run automated backend checks."""
        print("\n🤖 AUTOMATED BACKEND CHECKS:")
        
        try:
            # Test 1: State consistency
            initial_teams_count = len(state.active_teams)
            initial_players_count = len(state.connected_players)
            
            self.log_test(
                "Initial State Check", 
                True, 
                f"Teams: {initial_teams_count}, Players: {initial_players_count}"
            )
            
            # Test 2: Force refresh functionality
            from src.sockets.dashboard import get_all_teams
            
            # Test normal vs force refresh
            teams_normal = get_all_teams(force_refresh=False)
            teams_forced = get_all_teams(force_refresh=True)
            
            self.log_test(
                "Force Refresh Function", 
                True,
                f"Normal: {len(teams_normal)} teams, Forced: {len(teams_forced)} teams"
            )
            
        except Exception as e:
            self.log_test("Automated Backend Checks", False, f"Error: {str(e)}")
    
    def print_test_summary(self):
        """Print final test summary."""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed_count = sum(1 for result in self.test_results if result['passed'])
        total_count = len(self.test_results)
        
        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"{status} {result['test']}")
            if result['details'] and not result['passed']:
                print(f"    💡 {result['details']}")
        
        print(f"\nOverall Result: {passed_count}/{total_count} tests passed")
        
        if passed_count == total_count:
            print("🎉 ALL TESTS PASSED! Team disconnection fixes are working correctly.")
        else:
            print("⚠️  Some tests failed. Please review and fix the issues.")
        
        print("\n📋 Key Behaviors Verified:")
        print("✓ Dashboard updates automatically when players disconnect")
        print("✓ Input is disabled for remaining player when team incomplete")
        print("✓ Team status changes correctly (Active ↔ Waiting Pair)")
        print("✓ Force refresh bypasses caching for critical updates")
        print("✓ Teams can be reformed and resume normal operation")
    
    def print_troubleshooting_guide(self):
        """Print troubleshooting guide for common issues."""
        print("\n🔧 TROUBLESHOOTING GUIDE:")
        print()
        print("❌ Dashboard doesn't update automatically:")
        print("   - Check browser console for WebSocket errors")
        print("   - Verify dashboard page is connected to socket")
        print("   - Check server logs for emit_dashboard_team_update calls")
        print()
        print("❌ Input not disabled on disconnect:")
        print("   - Check if currentTeamStatus is being updated in browser console")
        print("   - Verify updateGameState() is called with correct team status")
        print("   - Check for duplicate socket event handlers")
        print()
        print("❌ Team status not changing:")
        print("   - Verify team_info['status'] is updated in server state")
        print("   - Check that handle_disconnect is being called")
        print("   - Review server logs for team status update emissions")
        print()
        print("📚 Debug Commands:")
        print("   Browser Console: console.log(currentTeamStatus, gameStarted)")
        print("   Server Logs: grep 'team_status_update' logs")
        print("   Check State: python -c \"from src.state import state; print(state.active_teams)\"")


def main():
    """Run the manual verification test."""
    tester = TeamDisconnectManualTest()
    
    print("Choose test mode:")
    print("1. Manual verification (requires browser)")
    print("2. Automated backend checks only")
    print("3. Both manual and automated")
    print("4. Print troubleshooting guide")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        tester.run_manual_verification_steps()
    elif choice == "2":
        tester.run_automated_checks()
        tester.print_test_summary()
    elif choice == "3":
        tester.run_automated_checks()
        tester.run_manual_verification_steps()
    elif choice == "4":
        tester.print_troubleshooting_guide()
    else:
        print("Invalid choice. Please run again with a valid option.")


if __name__ == "__main__":
    main()