# Automated Tests Design for CHSH-Game

## Overview
This document outlines the design for automated tests to be implemented for GitHub Actions CI to simulate server, host dashboard, and player/client interactions for the CHSH-Game application.

## Test Categories

### 1. Basic Functionality Tests
These tests verify that the core functionality of the application works as expected.

#### 1.1 Server Initialization Tests
- Test server startup and database initialization
- Verify server instance ID generation
- Test graceful shutdown handling

#### 1.2 Team Management Tests
- Test team creation
- Test joining existing teams
- Test leaving teams
- Test team reactivation after all players leave
- Test handling of duplicate team names

#### 1.3 Game Logic Tests
- Test game start/stop functionality
- Test round generation and assignment
- Test answer submission and validation
- Test score calculation and statistics

#### 1.4 Dashboard Tests
- Test dashboard client registration
- Test dashboard updates when teams/players change
- Test game control functions (start, pause, restart)
- Test statistics display and updates

### 2. User Interaction Flow Tests
These tests simulate real user interactions and workflows.

#### 2.1 Normal Game Flow
- Player 1 creates team
- Player 2 joins team
- Host starts game
- Players submit answers for multiple rounds
- Host views statistics
- Host ends game

#### 2.2 Edge Cases
- Player tries to join non-existent team
- Player tries to join full team
- Player submits invalid answers
- Player submits duplicate answers
- Host tries to start game with no teams
- Host tries to start game with incomplete teams

### 3. Browser Refresh Scenarios
These tests verify that the application handles browser refreshes correctly.

#### 3.1 Player Refresh Tests
- Test player refresh before joining team
- Test player refresh after creating team
- Test player refresh after joining team
- Test player refresh during active game
- Test player refresh after submitting answer

#### 3.2 Host Refresh Tests
- Test host refresh before starting game
- Test host refresh during active game
- Test host refresh after pausing game

### 4. Connection Stability Tests
These tests verify that the application handles connection issues gracefully.

#### 4.1 Slow Connection Tests
- Test slow client connections
- Test delayed answer submissions
- Test connection timeouts

#### 4.2 Server Performance Tests
- Test server under normal load
- Test server with simulated CPU throttling
- Test server with simulated memory constraints

### 5. Stress Tests
These tests verify that the application can handle high load.

#### 5.1 Concurrent User Tests
- Test with 10 concurrent teams (20 players)
- Test with 50 concurrent teams (100 players)
- Test with rapid answer submissions

#### 5.2 Long-Running Tests
- Test continuous gameplay for extended periods
- Test memory usage over time
- Test database performance with large datasets

## Implementation Approach

### Test Framework
- Use pytest as the primary testing framework
- Use pytest-cov for coverage reporting
- Use pytest-xdist for parallel test execution when appropriate

### Mocking and Simulation
- Use unittest.mock for mocking external dependencies
- Use socketio-client-nexus for simulating socket.io clients
- Use pytest-timeout for testing timeout scenarios

### Docker Integration
- Create a Dockerfile.test for test environment
- Use docker-compose for multi-container testing
- Configure GitHub Actions to build and run tests in Docker

### CI Pipeline Structure
1. Build test Docker image
2. Run unit tests
3. Run integration tests
4. Run browser refresh tests
5. Run connection stability tests
6. Run stress tests (optional based on resource constraints)
7. Generate and publish coverage report

## GitHub Actions Workflow

```yaml
name: CHSH-Game Tests

on:
  push:
    branches: [ main, master, develop ]
  pull_request:
    branches: [ main, master, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        pip install pytest pytest-cov pytest-timeout socketio-client-nexus
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v
    
    - name: Run integration tests
      run: |
        pytest tests/integration/ -v
    
    - name: Run browser refresh tests
      run: |
        pytest tests/browser_refresh/ -v
    
    - name: Run connection stability tests
      run: |
        pytest tests/connection/ -v
    
    - name: Run stress tests (small scale)
      run: |
        pytest tests/stress/small_scale.py -v
    
    - name: Generate coverage report
      run: |
        pytest --cov=src/ --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: false
```

## Docker Configuration

### Dockerfile.test
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pytest pytest-cov pytest-timeout socketio-client-nexus

COPY . .

CMD ["pytest", "-v"]
```

### docker-compose.test.yml
```yaml
version: '3'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.test
    ports:
      - "5000:5000"
    command: gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:5000
    environment:
      - FLASK_ENV=testing
  
  test:
    build:
      context: .
      dockerfile: Dockerfile.test
    depends_on:
      - app
    environment:
      - SERVER_URL=http://app:5000
      - FLASK_ENV=testing
    command: pytest tests/ -v
```
