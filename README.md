# $\mathbb{CHSH}\text{-}\mathbb{GAME}$
[![cicd](https://img.shields.io/github/actions/workflow/status/TonyXTYan/CHSH-Game/python-tests.yml?label=ci%20cd&logo=githubactions&logoColor=white)](https://github.com/TonyXTYan/CHSH-Game/actions/workflows/python-tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/TonyXTYan/CHSH-Game?token=4A0LZVD95V&logo=codecov&logoColor=white)](https://app.codecov.io/gh/TonyXTYan/CHSH-Game/)


## How to play 

As of May 2025, this game is hosted on free tier of `render.com` and only supports one game instance at a time (over the entire interenet, so I will be using this myself). If you want to host your own game, you can simply fork this repository and deploy your own instance. 

Presenter/Host: [https://chsh-game.onrender.com/dashboard](https://chsh-game.onrender.com/dashboard)

Player: [https://chsh-game.onrender.com/](https://chsh-game.onrender.com/)

![Host QR Code](/src/resources/qrcode-render-dashboard-framed-256.png)
![Player QR Code](/src/resources/qrcode-render-player-framed-256.png)


- To play this game, you need at least two players, the more the better. 
    - Each team will be two players, and they will be asked a series of questions (**A**,**B**,**X**,**Y**).
    - Each player within a team may get asked a different question, and they will have to answer either **True** or **False**.
    - They can discuss a strategy before the game starts, but they should not communicate to each other during the game.
    - Winning condition: 
        - Round 1. If both players get asked the same question, they should answer the same and answer **True**/**False** about half the time. 
          i.e. highest score of "Balanced Random" wins.
        - Round 2. When one player is asked **B** and the other player is asked **Y**, they should answer the same and answer **True**/**False** as much as possible.
          i.e. highest score of "CHSH Value" wins.


## The Physics


## How to deploy

Build commands
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Deploying locally
```
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```


Start command on `render.com`
```
gunicorn wsgi:app --worker-class eventlet
```


# TODO
- [ ] details stats shouldn't stream, should be on request, it also needs auto update upon team stats change
- [ ] clear past teams
- [ ] perhaps use cookies to store game state?
- [ ] compact rows 
- [ ] ± statistics  
- [ ] Bug, sometimes after reforming (reactivating) a team then inputs are disabled??
- [ ] Optimise CHSH normalisation
- [ ] Put a crown on winning team