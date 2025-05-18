# $\mathbb{CHSH}\text{-}\mathbb{GAME}$
[![cicd](https://img.shields.io/github/actions/workflow/status/TonyXTYan/CHSH-Game/python-tests.yml?label=ci%20cd&logo=githubactions&logoColor=white)](https://github.com/TonyXTYan/CHSH-Game/actions/workflows/python-tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/TonyXTYan/CHSH-Game?token=4A0LZVD95V&logo=codecov&logoColor=white)](https://app.codecov.io/gh/TonyXTYan/CHSH-Game/)


## How to play (as of 2025 May)


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
