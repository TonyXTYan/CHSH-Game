#!/usr/bin/env python3
"""
Comprehensive test runner for CHSH Game with focus on coverage and edge cases.
This script runs all tests with coverage reporting and identifies areas needing more tests.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_coverage_tests():
    """Run tests with coverage reporting"""
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🧪 Running comprehensive test suite with coverage analysis...")
    print("=" * 70)
    
    # Install dependencies if needed
    print("\n📦 Installing test dependencies...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "pytest-cov", "pytest-xdist", "pytest-mock", "numpy"
    ], check=False)
    
    # Run tests with coverage
    coverage_cmd = [
        sys.executable, "-m", "pytest",
        "--cov=src",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--cov-report=xml:coverage.xml",
        "--cov-fail-under=80",  # Require 80% coverage
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "-x",  # Stop on first failure for quick feedback
        "tests/"
    ]
    
    print(f"\n🔍 Running: {' '.join(coverage_cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(coverage_cmd, check=True)
        print("\n✅ All tests passed with sufficient coverage!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed or coverage below threshold. Exit code: {e.returncode}")
        print("\n📊 Coverage report generated in htmlcov/index.html")
        return e.returncode
    
    # Run specific physics/math validation tests
    print("\n🔬 Running physics/math validation tests...")
    physics_cmd = [
        sys.executable, "-m", "pytest", 
        "tests/unit/test_physics_calculations.py",
        "-v", "--tb=long"
    ]
    
    try:
        subprocess.run(physics_cmd, check=True)
        print("✅ Physics calculations validated!")
    except subprocess.CalledProcessError:
        print("❌ Physics validation failed!")
        return 1
    
    # Run edge case tests
    print("\n🚨 Running edge case and stress tests...")
    edge_case_cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/test_server_client_edge_cases.py",
        "tests/unit/test_game_logic_advanced.py",
        "-v", "--tb=short"
    ]
    
    try:
        subprocess.run(edge_case_cmd, check=True)
        print("✅ Edge cases handled correctly!")
    except subprocess.CalledProcessError:
        print("❌ Edge case tests failed!")
        return 1
    
    # Generate final coverage report
    print("\n📈 Generating detailed coverage report...")
    
    # Check if coverage data exists
    if Path(".coverage").exists():
        # Generate coverage summary
        subprocess.run([
            sys.executable, "-m", "coverage", "report", 
            "--show-missing", "--precision=2"
        ], check=False)
        
        print(f"\n📊 Detailed HTML coverage report: {project_root}/htmlcov/index.html")
        print(f"📄 XML coverage report: {project_root}/coverage.xml")
    
    print("\n🎯 Test Coverage Analysis Complete!")
    print("=" * 70)
    return 0

def run_specific_test_categories():
    """Run specific categories of tests to identify weak areas"""
    
    test_categories = {
        "Physics & Math": [
            "tests/unit/test_physics_calculations.py",
            "-k", "chsh or correlation or bell or quantum"
        ],
        "Server-Client Edge Cases": [
            "tests/unit/test_server_client_edge_cases.py",
            "-k", "race or timeout or malformed or concurrent"
        ],
        "Game Logic Advanced": [
            "tests/unit/test_game_logic_advanced.py", 
            "-k", "deterministic or fairness or entropy"
        ],
        "Integration Tests": [
            "tests/integration/",
            "-k", "interaction"
        ],
        "Database & State": [
            "tests/unit/test_models.py",
            "tests/unit/test_state.py"
        ]
    }
    
    print("\n🔍 Running specialized test categories...")
    
    for category, test_args in test_categories.items():
        print(f"\n📂 Testing: {category}")
        print("-" * 40)
        
        cmd = [sys.executable, "-m", "pytest"] + test_args + ["-v"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {category}: PASSED")
            else:
                print(f"❌ {category}: FAILED")
                print(f"Error output: {result.stderr}")
        except Exception as e:
            print(f"⚠️  {category}: ERROR - {e}")

def analyze_test_gaps():
    """Analyze potential gaps in test coverage"""
    
    print("\n🔍 Analyzing potential test coverage gaps...")
    print("-" * 50)
    
    # Areas that commonly need more testing
    critical_areas = {
        "Error Handling": [
            "Database transaction failures",
            "Network interruptions", 
            "Malformed client data",
            "Memory exhaustion scenarios"
        ],
        "Concurrency": [
            "Race conditions in team creation",
            "Simultaneous answer submissions", 
            "Cache invalidation conflicts",
            "Multiple dashboard connections"
        ],
        "Physics Validation": [
            "Bell inequality bounds",
            "Correlation matrix symmetry",
            "Statistical uncertainty propagation",
            "CHSH value theoretical limits"
        ],
        "Security": [
            "Session hijacking prevention",
            "Input sanitization",
            "SQL injection protection",
            "XSS prevention in team names"
        ]
    }
    
    for area, items in critical_areas.items():
        print(f"\n📋 {area}:")
        for item in items:
            print(f"   • {item}")
    
    print("\n💡 Recommendations:")
    print("   • Add stress tests with 1000+ concurrent users")
    print("   • Test with network latency simulation")
    print("   • Validate against quantum physics literature")
    print("   • Add property-based testing for game logic")
    print("   • Test database performance under load")

if __name__ == "__main__":
    print("🧪 CHSH Game - Comprehensive Test Coverage Analysis")
    print("=" * 70)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--categories":
        run_specific_test_categories()
        analyze_test_gaps()
    else:
        exit_code = run_coverage_tests()
        if exit_code == 0:
            analyze_test_gaps()
        sys.exit(exit_code)