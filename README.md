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

**CHSH Game** is an real-time multiplayer web app of the CHSH (Clauser-Horne-Shimony-Holt) Bell's inequality. 
Teams of two players answer random A/B/X/Y questions while a host dashboard tracks scores and CHSH statistics.

- Live demo: 
    - ⚠️ As of May 2025, this game is hosted on the free[\*](https://community.fly.io/t/clarification-on-fly-ios-free-tier-and-billing-policy/20909/4)[^](https://fly.io/docs/about/pricing/) tier on [fly.io](https://fly.io) (Sydney server) and it only supports one game instance at a time across the entire interenet. If you wish to host your own game or development, you can simply fork this repo and deploy your own instance. 
    - ⚠️ If you splot a live game is going on, please don't interrupt it, this repo can be easily deployed with [Flask](https://flask.palletsprojects.com/) and [Gunicorn](https://gunicorn.org/) for free on e.g. [render.com](https://render.com), which I have an instance hosted there too that you can freely play with.
    - Host: [chsh-game.***fly.dev***/dashboard](https://chsh-game.fly.dev/dashboard) ([chsh-game.on***render.com***/dashboard](https://chsh-game.onrender.com/dashboard))
    - Player: [chsh-game.***fly.dev***](https://chsh-game.fly.dev) ([chsh-game.on***render.com***](https://chsh-game.onrender.com))

![Player QR Code](https://genqrcode.com/embedded?style=0&inner_eye_style=0&outer_eye_style=0&logo=null&color=%23000000FF&background_color=%23FFFFFF&inner_eye_color=%23000000&outer_eye_color=%23000000&imageformat=svg&language=en&frame_style=0&frame_text=SCAN%20ME&frame_color=%23000000&invert_colors=false&gradient_style=0&gradient_color_start=%23FF0000&gradient_color_end=%237F007F&gradient_start_offset=5&gradient_end_offset=95&stl_type=1&logo_remove_background=null&stl_size=100&stl_qr_height=1.5&stl_base_height=2&stl_include_stands=false&stl_qr_magnet_type=3&stl_qr_magnet_count=0&type=0&text=https%3A%2F%2Fchsh-game.fly.dev&width=300&height=300&bordersize=2)



### New! v2.0.0
The game now supports two modes:
- **Classic Mode** Standard CHSH Bell Test game in the style of how physics experiments are done.
- **New Mode** Implementation of the CHSH game where player 1 only need to answer A/B questions, and player 2 only need to answer X/Y questions. 


## How to play
TODO

<details>
<summary>Abstract Q&As (click to unfold)</summary>

- The game is designed to be played in a group setting, such as a classroom, auditorium, or at pubs. 

- This game requires **at least two players** (one team of two), though it's more fun with more teams. 
- In each round: 
    - Each player is idependently assigned a random questions: **A**,**B**,**X** or **Y**.  
    - Players respond with either **True** or **False**, base on a shared strategy agreed upon before the game starts.
    - ***No communicate*** is allowed during the game! 

**Winning condition:**
- Highest **balanced ⏐⟨Tr⟩⏐ 🎯** (consistency):
  - If both players are asked the same question (A/A, B/B, X/X, or Y/Y), they should give the **same** answer. 
    - Trace/4 = ⟨Tr⟩ = ±1 if partners always agree, and 0 if players always disagrees.
    - Balance = 1 if answers to each question is True/False about 50:50 of the time, and 0 if always the same.
    - Balanced |⟨Tr⟩| = 0.5 * (balance + |⟨Tr⟩|); higher is better.
- Best **CHSH 🏆** (non-local correlation):
  - If one player is asked **B** and the other is asked **Y**, they have to answer **differently** as much as possible, i.e. one True and one False.
  - For any other question pair, you have to give same response as much as possible.
</details>

<details>
<summary>Winning Strategy (click to unfold)</summary>

#### Normal human strategy
Note the following response table

| Question | A | B | X | Y |
|---|---|---|---|---|
| Response | T | T | T | F |

This strategy wins ⏐⟨Tr⟩⏐ = 1 and CHSH = 2.
To have balance = 1, two players need to share a sequence bit bits $\{b_i\}$ where $b_i = 0$ means using the table and $b_i = 1$ means using the negation of the table, i.e. (F,F,F,T), this sequence could simply be even/odd bits of the current round number.

### Quantum strategy
See below

</details>

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
E(\theta_A, \theta_B) = 
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


## Load Testing
The `chsh_load_test.py` script simulates many teams and players. See [`LOAD_TEST_README.md`](load_test/LOAD_TEST_README.md) for more details.


## Acknowledgements
- More than 99% of the code are AI generated, thanks to GitHub Copilot, ChatGPT, Cursor, Manus, DeepSeek, Antropic, Qwen and more. Probably, more than few billion tokens got burned up in generating this app. 


