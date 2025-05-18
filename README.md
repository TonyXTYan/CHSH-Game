# $\mathbb{CHSH}\text{-}\mathbb{GAME}$

## How to play 


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

