# CHSH Game Documentation

Welcome to the comprehensive documentation for the CHSH Game project - a multiplayer web-based implementation of the Clauser-Horne-Shimony-Holt quantum game that demonstrates Bell's inequality and quantum entanglement concepts.

## Table of Contents

### Getting Started
- [Installation Guide](installation.md) - Setup and installation instructions
- [Quick Start](installation.md#quick-start) - Get the game running locally in minutes
- [Game Rules](game-rules.md) - How to play the CHSH game

### Technical Documentation
- [Architecture Overview](architecture.md) - System design and component overview
- [API Documentation](api.md) - Socket.IO events and data structures
- [Development Guide](development.md) - Code structure and development workflow
- [Testing Guide](testing.md) - Running tests and test architecture

### Deployment & Operations
- [Deployment Guide](deployment.md) - Deploy to various platforms (Fly.io, Render.com, etc.)
- [Troubleshooting](troubleshooting.md) - Common issues and solutions

### Physics & Theory
- [The Physics Behind CHSH](physics.md) - Understanding the quantum mechanics concepts

## About This Project

The CHSH Game is a real-time multiplayer web application that allows teams to participate in a quantum game demonstration. Players answer binary questions (A/B/X/Y) while a host monitors statistics including CHSH values, correlations, and quantum-classical boundaries.

### Key Features
- **Real-time multiplayer gameplay** via Socket.IO
- **Interactive dashboard** for hosts/presenters
- **Multiple game modes**: Classic, Simplified, and AQM Joe themes
- **Live statistics** including CHSH values, balance, and trace calculations
- **Data export** capabilities for educational analysis
- **Responsive design** for desktop and mobile
- **Load testing** framework for scalability testing

### Technology Stack
- **Backend**: Python, Flask, Flask-SocketIO, SQLAlchemy
- **Frontend**: HTML5, CSS3, JavaScript ES6+, Socket.IO Client
- **Database**: SQLite (development), PostgreSQL (production)
- **Deployment**: Gunicorn with Eventlet worker class
- **Testing**: pytest with comprehensive integration tests

## Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| Set up the game locally | [Installation Guide](installation.md) |
| Understand how to play | [Game Rules](game-rules.md) |
| Learn about the architecture | [Architecture Overview](architecture.md) |
| Contribute to development | [Development Guide](development.md) |
| Deploy to production | [Deployment Guide](deployment.md) |
| Understand the physics | [Physics Documentation](physics.md) |
| Integrate with the API | [API Documentation](api.md) |
| Fix issues | [Troubleshooting](troubleshooting.md) |

## Project Status

- **Current Version**: Latest stable release
- **License**: MIT License
- **CI/CD**: GitHub Actions with automated testing
- **Code Coverage**: Available via Codecov
- **Live Demo**: Hosted on Fly.io and Render.com

For questions, issues, or contributions, please visit the [GitHub repository](https://github.com/TonyXTYan/CHSH-Game).