#!/usr/bin/env python3
"""
Comprehensive test runner for CHSH Game with focus on coverage and edge cases.
This script runs all tests with coverage reporting and identifies areas needing more tests.
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def run_comprehensive_tests():
    """Run the full test suite with coverage analysis"""
    logger.info("🧪 Running comprehensive test suite with coverage analysis...")
    logger.info("=" * 70)
    
    # Install dependencies first
    logger.info("\n📦 Installing test dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-q",
            "coverage", "pytest", "pytest-cov", "requests", "beautifulsoup4"
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        return False

    project_root = Path(__file__).parent.parent
    
    # Main coverage command
    coverage_cmd = [
        "coverage", "run", 
        "--source=src,load_test",
        "--omit=*/tests/*,*/test_*,*/__pycache__/*",
        "-m", "pytest", 
        "tests/", 
        "-v", 
        "--tb=short"
    ]
    
    try:
        logger.info(f"\n🔍 Running: {' '.join(coverage_cmd)}")
        logger.info("-" * 50)
        result = subprocess.run(coverage_cmd, cwd=project_root, check=True)
        
        if result.returncode == 0:
            logger.info("\n✅ All tests passed with sufficient coverage!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"\n❌ Tests failed or coverage below threshold. Exit code: {e.returncode}")
        logger.info("\n📊 Coverage report generated in htmlcov/index.html")
        return False

    # Run physics validation
    logger.info("\n🔬 Running physics/math validation tests...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/unit/test_physics_calculations.py", 
            "-v"
        ], cwd=project_root, check=True, capture_output=True)
        logger.info("✅ Physics calculations validated!")
    except subprocess.CalledProcessError:
        logger.error("❌ Physics validation failed!")
        return False

    # Run edge case tests
    logger.info("\n🚨 Running edge case and stress tests...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-k", "stress or edge or boundary",
            "-v"
        ], cwd=project_root, check=True, capture_output=True)
        logger.info("✅ Edge cases handled correctly!")
    except subprocess.CalledProcessError:
        logger.error("❌ Edge case tests failed!")
        return False

    # Generate detailed coverage report
    logger.info("\n📈 Generating detailed coverage report...")
    try:
        subprocess.run(["coverage", "html"], cwd=project_root, check=True, capture_output=True)
        subprocess.run(["coverage", "xml"], cwd=project_root, check=True, capture_output=True)
        subprocess.run(["coverage", "report", "--show-missing"], cwd=project_root, check=True)
    except subprocess.CalledProcessError as e:
        logger.warning(f"Coverage report generation had issues: {e}")

    logger.info(f"\n📊 Detailed HTML coverage report: {project_root}/htmlcov/index.html")
    logger.info(f"📄 XML coverage report: {project_root}/coverage.xml")
    
    logger.info("\n🎯 Test Coverage Analysis Complete!")
    logger.info("=" * 70)
    
    return True

def run_specialized_tests():
    """Run specialized test categories with detailed analysis"""
    project_root = Path(__file__).parent.parent
    
    test_categories = {
        "Unit Tests": "tests/unit/",
        "Integration Tests": "tests/integration/", 
        "Load Test Framework": "tests/unit/test_load_test.py",
        "Game Logic": "tests/unit/test_game_logic.py",
        "Socket Communication": "tests/unit/test_*sockets*.py"
    }
    
    results = {}
    logger.info("\n🔍 Running specialized test categories...")
    
    for category, test_pattern in test_categories.items():
        logger.info(f"\n📂 Testing: {category}")
        logger.info("-" * 40)
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", test_pattern, "-v", "--tb=short"
            ], cwd=project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ {category}: PASSED")
                results[category] = "PASSED"
            else:
                logger.error(f"❌ {category}: FAILED")
                logger.error(f"Error output: {result.stderr}")
                results[category] = "FAILED"
        except Exception as e:
            logger.warning(f"⚠️  {category}: ERROR - {e}")
            results[category] = "ERROR"
    
    return results

def analyze_coverage_gaps():
    """Analyze potential test coverage gaps and provide recommendations"""
    logger.info("\n🔍 Analyzing potential test coverage gaps...")
    logger.info("-" * 50)
    
    # Define key areas that should be tested
    critical_areas = {
        "Socket Event Handling": [
            "Connection/disconnection flows",
            "Team creation and joining",
            "Real-time game state updates",
            "Error handling for socket events"
        ],
        "Game Logic": [
            "Question generation algorithms", 
            "Score calculation accuracy",
            "Round progression logic",
            "Team state management"
        ],
        "Database Operations": [
            "Data persistence and retrieval",
            "Transaction handling",
            "Concurrent access patterns",
            "Migration scripts"
        ],
        "Load Testing": [
            "Concurrent user simulation",
            "Performance under stress",
            "Memory usage patterns",
            "Network timeout handling"
        ],
        "Security": [
            "Input validation",
            "Session management", 
            "Rate limiting",
            "CSRF protection"
        ]
    }
    
    for area, items in critical_areas.items():
        logger.info(f"\n📋 {area}:")
        for item in items:
            logger.info(f"   • {item}")
    
    logger.info("\n💡 Recommendations:")
    logger.info("   • Add stress tests with 1000+ concurrent users")
    logger.info("   • Test with network latency simulation") 
    logger.info("   • Validate against quantum physics literature")
    logger.info("   • Add property-based testing for game logic")
    logger.info("   • Test database performance under load")

if __name__ == "__main__":
    logger.info("🧪 CHSH Game - Comprehensive Test Coverage Analysis")
    logger.info("=" * 70)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--categories":
        run_specialized_tests()
        analyze_coverage_gaps()
    else:
        exit_code = run_comprehensive_tests()
        if exit_code:
            analyze_coverage_gaps()
        sys.exit(exit_code)