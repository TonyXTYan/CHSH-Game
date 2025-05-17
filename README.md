$\mathbb{CHSH}-\mathbb{G}\text{ame}$


Deploying locally
```
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```


Start command on render.com 
```
gunicorn wsgi:app --worker-class eventlet
```


