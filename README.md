# $\mathbb{CHSH}\text{-}\mathbb{GAME}$
[![GitHub Release](https://img.shields.io/github/v/release/TonyXTYan/CHSH-Game?label=latest%20release)](https://github.com/TonyXTYan/CHSH-Game/releases/latest)
![GitHub last commit](https://img.shields.io/github/last-commit/TonyXTYan/CHSH-Game)
[![License](https://img.shields.io/github/license/TonyXTYan/CHSH-Game?color=blue)](https://github.com/TonyXTYan/CHSH-Game/blob/main/LICENSE)
[![cicd](https://img.shields.io/github/actions/workflow/status/TonyXTYan/CHSH-Game/python-tests.yml?label=ci%20cd&logo=githubactions&logoColor=white)](https://github.com/TonyXTYan/CHSH-Game/actions/workflows/python-tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/TonyXTYan/CHSH-Game?token=4A0LZVD95V&logo=codecov&logoColor=white)](https://app.codecov.io/gh/TonyXTYan/CHSH-Game/)

[![Python](https://img.shields.io/badge/python-3.12-gray.svg?style=flat&logo=python&logoColor=white&labelColor=black)](https://docs.python.org/3/whatsnew/3.12.html)
[![Socket.io](https://img.shields.io/badge/socket.io-black?logo=socketdotio&logoColor=white)](https://socket.io/)
[![Flask](https://img.shields.io/badge/flask-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gunicorn](https://img.shields.io/badge/gunicorn-black?logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![render](https://img.shields.io/badge/render-black?logo=render&logoColor=white)](https://render.com/)




## Overview

**CHSH Game** is a multiplayer, web-based implementation of the famous quantum CHSH Bell's inequality. 
It allows teams to compete in a game to explore quantum-classical boundaries. This project also features a real-time dashboard of the CHSH parameters and various statistics.

- Live demo: 
    - ⚠️ As of May 2025, this game is hosted with a free tier on [render.com](https://render.com) and it only supports one game instance at a time (over the entire interenet). **This also means the server might take a minute to wake up after some inactivity.** If you wish to host your own game or doing extensive testing, you can simply fork this repository and deploy your own instance. That is, if you see a live game is going on, please don't interrupt it, this repo can be easily deployed with flask and gunicorn (and for free on e.g. [render.com](https://render.com)).
    - Host: [https://chsh-game.onrender.com/dashboard](https://chsh-game.onrender.com/dashboard)
    - Player: [https://chsh-game.onrender.com/](https://chsh-game.onrender.com/)

![Host QR Code](/src/resources/qrcode-render-dashboard-framed-256.png)
![Player QR Code](/src/resources/qrcode-render-player-framed-256.png)
<!-- https://genqrcode.com -->



Presenter/Host: [https://chsh-game.onrender.com/dashboard](https://chsh-game.onrender.com/dashboard)

Player: [https://chsh-game.onrender.com/](https://chsh-game.onrender.com/)


## How to play
- The game is designed to be played in a group setting, such as a classroom, auditorium, or at pubs.

- To play this game, you need **at least two players** (one team of two), the more the better. 
    - Each round, every players in a team receive a randomly selected questions (**A**,**B**,**X**,**Y**), each player gets their own random question.
    - Players answer either **True** or **False** independently.  
    - They can discuss a strategy before the game starts, but they should *not communicate* to each other during the game.
    - ***Winning condition:*** 
        - **Session 1.** If both players get asked the same question, they should answer the same and answer **True**/**False** about half the time. 
          i.e. highest score of "Balanced ⏐⟨Tr⟩⏐" wins. 
            - Winning team is awarded the badge 🎯.
        - **Session 2.** When one player is asked **B** and the other player is asked **Y**, they should answer the same and answer **True**/**False** as much as possible. 
          i.e. highest score of "CHSH Value" wins.
            - Winning team is awarded the badge 🏆.


## The Physics
TODO 

[CHSH Inequality - Wikipedia](https://en.wikipedia.org/wiki/CHSH_inequality)

[LHVT - Wikipedia](https://en.wikipedia.org/wiki/Local_hidden-variable_theory)

[Bell's test - Wikipedia](https://en.wikipedia.org/wiki/Bell_test)

[2022 Nobel Prize in Physics](https://www.nobelprize.org/prizes/physics/2022/summary/)


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
Feel free to change the port number `8080` in the command above.

**Deploying to Render.com:**  
Start command:  
```bash
gunicorn wsgi:app --worker-class eventlet
```


# TODO
- [ ] details stats shouldn't stream, should be on request, it also needs auto update upon team stats change
- [ ] button clear all inactive teams
- [ ] perhaps use cookies to store game state?
- [ ] compact rows
- [ ] multiple simultaneous games
- [x] ± statistics
- [x] Bug, sometimes after reforming (reactivating) a team then inputs are disabled??
- [x] Optimise CHSH normalisation
- [x] Put a crown on winning team