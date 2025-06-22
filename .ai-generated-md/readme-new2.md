# $\mathbb{CHSH}\text{-}\mathbb{GAME}$

[![cicd](https://img.shields.io/github/actions/workflow/status/TonyXTYan/CHSH-Game/python-tests.yml?label=ci%20cd&logo=githubactions&logoColor=white)](https://github.com/TonyXTYan/CHSH-Game/actions/workflows/python-tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/TonyXTYan/CHSH-Game?token=4A0LZVD95V&logo=codecov&logoColor=white)](https://app.codecov.io/gh/TonyXTYan/CHSH-Game/)

---

## Overview

**CHSH Game** is a multiplayer, web-based implementation of the famous quantum CHSH game. It allows teams to compete in a nonlocal game, visualize statistics, and explore quantum-classical boundaries. The project features a real-time dashboard, QR code joining, and detailed analytics.

- **Live Demo:**  
  - Host: [https://chsh-game.onrender.com/dashboard](https://chsh-game.onrender.com/dashboard)  
  - Player: [https://chsh-game.onrender.com/](https://chsh-game.onrender.com/)  
  - ⚠️ Hosted on free tier; only one game instance at a time. Server may take up to a minute to wake up after inactivity.

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [How to Play](#how-to-play)
- [The Physics](#the-physics)
- [Quick Start / Local Deployment](#quick-start--local-deployment)
- [Project Structure](#project-structure)
- [FAQ](#faq)
- [Acknowledgments](#acknowledgments)
- [Contributing](#contributing)
- [License](#license)
- [TODO](#todo)

---

## Features

- Multiplayer CHSH game with web interface
- Real-time dashboard for hosts/presenters
- Team creation, joining, and reactivation
- QR code links for easy joining
- Live statistics: CHSH value, balance, trace, and more
- Downloadable answer logs (CSV)
- Responsive UI for desktop and mobile
- Socket.IO-based real-time updates

---

## Screenshots

> Replace these placeholders with real screenshots.

![Player View](docs/screenshot-player.png)
*Player interface for answering questions.*

![Dashboard View](docs/screenshot-dashboard.png)
*Presenter dashboard with live stats and team management.*

---

## How to Play

**Host/Presenter:**  
- Open the [Dashboard](https://chsh-game.onrender.com/dashboard) to manage teams and start the game.

**Players:**  
- Open the [Player Link](https://chsh-game.onrender.com/) or scan the QR code below to join.

![Host QR Code](/src/resources/qrcode-render-dashboard-framed-256.png)
![Player QR Code](/src/resources/qrcode-render-player-framed-256.png)

### Game Rules

- At least two players required (teams of two).
- Each round, both players in a team receive a question (**A**, **B**, **X**, or **Y**).
- Players answer **True** or **False** independently (no communication during the game).
- **Round 1:** If both players get the same question, they should answer the same, and answers should be balanced between True/False.
- **Round 2:** If one gets **B** and the other **Y**, they should answer the same as often as possible.
- **Winning:**  
  - Highest "Balanced Random" score wins Round 1.  
  - Highest "CHSH Value" wins Round 2.

---

## The Physics

The CHSH game is a test of quantum nonlocality. It demonstrates how quantum strategies can outperform classical ones in certain cooperative games. For more, see [CHSH game on Wikipedia](https://en.wikipedia.org/wiki/CHSH_inequality).

---

## Quick Start / Local Deployment

**Clone and set up:**
```bash
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Run locally:**
```bash
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```
Visit [http://localhost:8080/](http://localhost:8080/) for the player view, and [http://localhost:8080/dashboard](http://localhost:8080/dashboard) for the dashboard.

**Deploying to Render.com:**  
Start command:  
```
gunicorn wsgi:app --worker-class eventlet
```

---

## Project Structure

```
src/
├── routes/      # Flask routes for static files and user API
├── static/      # Frontend assets (HTML, JS, CSS)
├── sockets/     # Socket.IO event handlers (game, dashboard, teams)
├── models/      # SQLAlchemy models (Teams, Answers, Rounds, Users)
├── game_logic.py # Core game logic and round management
├── config.py     # App and database configuration
├── state.py      # In-memory state management
├── main.py       # App entry point
```

---

## FAQ

**Q: Can I host multiple games at once?**  
A: The public demo supports only one game instance at a time. To host your own, fork and deploy your own instance.

**Q: Why does the server take a while to start?**  
A: Free hosting may put the server to sleep after inactivity.

**Q: How do I reset the game?**  
A: Use the dashboard's "Reset game stats" button.

---

## Acknowledgments

- Inspired by the CHSH game from quantum information theory.
- Built with Flask, Socket.IO, and SQLAlchemy.
- Thanks to all contributors and testers.

---

## Contributing

Pull requests and issues are welcome!  
- Fork the repo and create a feature branch.
- Open a PR with a clear description.
- For major changes, please open an issue first.

---

## License

Specify your license here (e.g., MIT, Apache 2.0).

---

## TODO

- [ ] Details stats shouldn't stream, should be on request, it also needs auto update upon team stats change
- [ ] Clear past teams
- [ ] Perhaps use cookies to store game state?
- [ ] Compact rows
- [ ] ± statistics
- [ ] Bug: sometimes after reforming (reactivating) a team then inputs are disabled?
- [ ] Optimise CHSH normalisation
- [ ] Put a crown on winning team
