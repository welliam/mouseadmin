# save this as app.py
import os
from flask import Flask, render_template

from mouseadmin import neocities


app = Flask(__name__)





@app.route("/reviews")
def reviews():
    client = neocities.NeoCities(api_key=os.getenv("MOUSEADMIN_SITE_API_KEY"))
    items = client.listitems()["files"]
    review_items = [item for item in items if "reviews/" in item['path']]
    return render_template("review_list.html", items=review_items)
