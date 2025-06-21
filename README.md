# $\mathbb{CHSH}\text{-}\mathbb{GAME}$
[![GitHub Release](https://img.shields.io/github/v/release/TonyXTYan/CHSH-Game?label=latest%20release)](https://github.com/TonyXTYan/CHSH-Game/releases/latest)
![GitHub last commit](https://img.shields.io/github/last-commit/TonyXTYan/CHSH-Game)
[![License](https://img.shields.io/github/license/TonyXTYan/CHSH-Game?color=blue)](https://github.com/TonyXTYan/CHSH-Game/blob/main/LICENSE)
[![cicd](https://img.shields.io/github/actions/workflow/status/TonyXTYan/CHSH-Game/python-tests.yml?label=ci%20cd&logo=githubactions&logoColor=white)](https://github.com/TonyXTYan/CHSH-Game/actions/workflows/python-tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/TonyXTYan/CHSH-Game?token=4A0LZVD95V&logo=codecov&logoColor=white)](https://app.codecov.io/gh/TonyXTYan/CHSH-Game/)

[![Python](https://img.shields.io/badge/python-3.11-grey.svg?style=flat&logo=python&logoColor=white&labelColor=black)](https://docs.python.org/3/whatsnew/3.12.html)
[![Socket.io](https://img.shields.io/badge/socket.io-black?logo=socketdotio&logoColor=white)](https://socket.io/)
[![Flask](https://img.shields.io/badge/flask-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gunicorn](https://img.shields.io/badge/gunicorn-black?logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![render](https://img.shields.io/badge/render-black?logo=render&logoColor=white)](https://render.com/)
[![Fly.io](https://img.shields.io/badge/fly.io-black?logo=flydotio&logoColor=white)](https://fly.io/)
[![Eventlet](https://img.shields.io/badge/eventlet-black?logo=eventlet&logoColor=white)](https://eventlet.net/)



## Overview

**CHSH Game** is a multiplayer, web-based implementation of the famous quantum CHSH Bell's inequality. 
It allows teams to compete in a game to explore quantum-classical boundaries. This project also features a real-time dashboard of the CHSH parameters and various statistics. Currently it support upto 30 teams (60 players).

- Live demo: 
    - ⚠️ As of May 2025, this game is hosted on the free[\*](https://community.fly.io/t/clarification-on-fly-ios-free-tier-and-billing-policy/20909/4)[^](https://fly.io/docs/about/pricing/) tier on [fly.io](https://fly.io) (Sydney server) and it only supports one game instance at a time across the entire interenet. If you wish to host your own game or development, you can simply fork this repo and deploy your own instance. 
    - ⚠️ If you splot a live game is going on, please don't interrupt it, this repo can be easily deployed with [Flask](https://flask.palletsprojects.com/) and [Gunicorn](https://gunicorn.org/) for free on e.g. [render.com](https://render.com), which I have an instance hosted there too that you can freely play with.
    - Host: [chsh-game.***fly.dev***/dashboard](https://chsh-game.fly.dev/dashboard) ([chsh-game.on***render.com***/dashboard](https://chsh-game.onrender.com/dashboard))
    - Player: [chsh-game.***fly.dev***](https://chsh-game.fly.dev) ([chsh-game.on***render.com***](https://chsh-game.onrender.com))

![Player QR Code](https://genqrcode.com/embedded?style=0&inner_eye_style=0&outer_eye_style=0&logo=null&color=%23000000FF&background_color=%23FFFFFF&inner_eye_color=%23000000&outer_eye_color=%23000000&imageformat=svg&language=en&frame_style=0&frame_text=SCAN%20ME&frame_color=%23000000&invert_colors=false&gradient_style=0&gradient_color_start=%23FF0000&gradient_color_end=%237F007F&gradient_start_offset=5&gradient_end_offset=95&stl_type=1&logo_remove_background=null&stl_size=100&stl_qr_height=1.5&stl_base_height=2&stl_include_stands=false&stl_qr_magnet_type=3&stl_qr_magnet_count=0&type=0&text=https%3A%2F%2Fchsh-game.fly.dev&width=300&height=300&bordersize=2)



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

This game ask players to respond to questions, {A, B} and {X, Y},  
these correspond a measurement of the Bell state 
$$
\left| \psi \right\rangle = \frac{1}{\sqrt{2}} \left( \left| \uparrow_z \uparrow_z \right\rangle + \left| \downarrow_z \downarrow_z \right\rangle \right)
$$
in the basis of 
$$
\hat \sigma_\theta = \cos(\theta) \hat \sigma_z + \sin(\theta) \hat \sigma_x 
= \begin{pmatrix}
\cos(\theta) & \sin(\theta) \\
\sin(\theta) & -\cos(\theta)  
\end{pmatrix}
$$
where $\hat \sigma_z$ and $\hat \sigma_x$ are the Pauli matrices,
and
$$
\begin{align}
\begin{cases}
A: & \theta = 0 \\
B: & \theta = \frac{\pi}{2}
\end{cases}
\quad
\begin{cases}
X: & \theta = \frac{+\pi}{4} \\
Y: & \theta = \frac{-\pi}{4}
\end{cases}
\end{align}
$$
are the relavent angles of the measurement.

Some algebra excercises can show the expectation value of 
$$
\mathcal P(\uparrow_{\theta_A} \uparrow_{\theta_B}) + 
\mathcal P(\downarrow_{\theta_A} \downarrow_{\theta_B}) -
\mathcal P(\uparrow_{\theta_A} \downarrow_{\theta_B}) -
\mathcal P(\downarrow_{\theta_A} \uparrow_{\theta_B}) 
= 
\left\langle \hat \sigma_{\theta_A} \hat \sigma_{\theta_B} \right\rangle
= 
\cos(\theta_A - \theta_B). 
$$

Hence getting the CHSH 
$$
\mathcal S = E(A, X) + E(A, Y) + E(B, X) - E(B, Y) = 2\sqrt 2.
$$


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

Untested
```bash
gunicorn wsgi:app --worker-class eventlet --workers 4
gunicorn wsgi:app --worker-class eventlet --workers 4 --bind 0.0.0.0:8080
```



## Acknowledgements
- \>99% of the code are AI generated, thanks to GitHub Copilot, ChatGPT, Manus, DeepSeek, Antropic and Qwen. Probably, more than 30 million tokens got burned up in generating this app. 



# TODOs
- [ ] button clear all inactive teams
- [ ] perhaps use cookies to store game state?
- [ ] compact rows
- [ ] multiple simultaneous games
- [x] ± statistics
- [x] Bug, sometimes after reforming (reactivating) a team then inputs are disabled??
- [x] Optimise CHSH normalisation
- [x] Put a crown on winning team
- [ ] fly.io deploy via CI
- [x] /about.html
- [ ] optimise server side CPU / RAM utilisation
- [ ] persistent storage of game state, re-downloadable, maybe use browser storage too?
- [ ] multiple game instances on multiple server machines
- [ ] more unit tests, increase coverage for now
- [ ] bug in the two CHSH value calc, once should be lower by 1/sqrt(2) ??

# Harder TODOs
- [ ] details stats shouldn't stream, should be on request, it also needs auto update upon team stats change
- [ ] batch load dashboard, i.e. don't instant update