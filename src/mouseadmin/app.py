# save this as app.py
from flask import Flask

from mouseadmin import neocities


app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello, World..."
