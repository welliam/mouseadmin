import sqlite3
from functools import cached_property
import time
from dateutil import parser
import requests
import tempfile
from slugify import slugify
from decimal import Decimal
import re
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
import os
from flask import Flask, render_template, request, redirect, g
from bs4 import BeautifulSoup
from typing import Optional
import pathlib

from mouseadmin import neocities



app = Flask(__name__)


NEOCITIES_PATH_REVIEW = "reviews/"

NEOCITIES_PATH_REVIEW_HOME = NEOCITIES_PATH_REVIEW + "home.html"

NEOCITIES_DOMAIN = os.getenv("NEOCITIES_DOMAIN", "https://fern.neocities.org")

API_KEY = os.getenv("MOUSEADMIN_SITE_API_KEY")

NON_REVIEW_PAGES = ["home.html", "faq.html"]


DATABASE = os.getenv("MOUSEADMIN_DB")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


@dataclass
class Template:
    name: str
    neocities_path: str
    template_jinja: str
    index_jinja: str


dataclass
class FileInfo:
    is_directory: bool
    path: str
    sha1_hash: str
    size: int
    updated_at: str
    created_at: str

    @classmethod
    def parse_files(cls, items, entry_paths) -> list["FileInfo"]:
        return [
            cls(**item)
            for item in items
            if any(item["path"].startswith(path) for path in entry_paths)
            and item["path"].endswith(".html")
            and not item["is_directory"]
            # TODO non review: make a table?
            and not any(non_review in item["path"] for non_review in NON_REVIEW_PAGES)
        ]


class CachedNeocitiesClient:
    _client: neocities.NeoCities

    def __init__(self):
        self._client = neocities.NeoCities(
            api_key=API_KEY,
        )

    @cached_property
    def items(self):
        print("LISTITEMS")
        return self._client.listitems()

    def fetch_reviews_info(self) -> list["ReviewInfo"]:
        items = self.items["files"]
        return ReviewInfo.parse_reviews(items)

    def get(self, path):
        ppath = pathlib.Path(f"cache/{path}")
        [review] = [r for r in self.fetch_reviews_info() if r.path == path.strip("/")]
        fetched = False
        if not ppath.exists() or (
            datetime.fromtimestamp(ppath.stat().st_mtime).astimezone()
            < review.updated_at_datetime
        ):
            print(f"FETCHING {path}")
            url = f"{NEOCITIES_DOMAIN}/{path}"
            text = requests.get(url).text
            open(f"cache/{path}", "w").write(text)
            fetched = True
        return fetched, open(f"cache/{path}").read()


class Dummy:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.setattr(key, value)


# @app.route("/review/refresh-all", methods=["POST"])
# def refresh_all():
#     client = MouseadminNeocitiesClient()
#     reviews = sorted(
#         [
#             review
#             for review in client.list_full_reviews()
#         ],
#         key=lambda review: review.date,
#         reverse=True,
#     )
#     reviews_dict = {
#         review.neocities_path: render_template(
#             "review.html",
#             **review.review_template_context(),
#         )
#         for review in reviews
#     }
#     client.upload_strings(
#         {
#             **reviews_dict,
#             NEOCITIES_PATH_REVIEW_HOME: render_template(
#                 "home.html", **client.fetch_home_context(reviews)
#             ),
#         }
#     )
#     return redirect("/review")


@app.route("/templates/new", methods=["GET", "POST"])
def new_template():
    if request.method == "GET":
        return render_template("template.html", template=None)
    else:
        db = get_db()
        template_name = request.form["template_name"]
        neocities_path = request.form["neocities_path"]
        index_template = request.form["index_template"]
        entry_path_template = request.form["entry_path_template"]
        entry_template = request.form["entry_template"]
        cur = db.execute("""
            insert into Template(name, neocities_path, entry_path_template, entry_template, index_template)
            values(?, ?, ?, ?, ?)
        """, (template_name, neocities_path, entry_path_template, entry_template, index_template))
        template_id = cur.lastrowid
        db.executemany("""
            insert into TemplateField(template_id, field_name, field_type, field_options)
            values(?, ?, ?, ?)
        """, [
            (template_id, field_name, field_type, None)
            for field_name, field_type in
            zip(request.form.getlist("field_name"), request.form.getlist("field_type"))
        ])
        db.commit()
        return redirect("/templates")


@app.route("/templates/<template_id>/update", methods=["POST"])
def update_template(template_id: int):
    db = get_db()
    template_name = request.form["template_name"]
    neocities_path = request.form["neocities_path"]
    index_template = request.form["index_template"]
    entry_path_template = request.form["entry_path_template"]
    entry_template = request.form["entry_template"]
    cur = db.execute("""
           update Template
           set name=?, neocities_path=?, entry_path_template=?, entry_template=?, index_template=?
           where id=?
    """, (template_name, neocities_path, entry_path_template, entry_template, index_template, template_id))
    db.execute("delete from TemplateField where template_id=?", template_id)
    db.executemany("""
           insert into TemplateField(template_id, field_name, field_type, field_options)
           values(?, ?, ?, ?)
       """, [
           (template_id, field_name, field_type, None)
           for field_name, field_type in
           zip(request.form.getlist("field_name"), request.form.getlist("field_type"))
       ])
    db.commit()
    return redirect("/templates")

@app.route("/templates/<template_id>/delete", methods=["POST"])
def delete_template(template_id: int):
    db = get_db()
    db.execute("delete Template where id=?", template_id)
    db.commit()
    return redirect("/templates")


@app.route("/templates", methods=["GET"])
def templates_list():
    db = get_db()
    templates = db.execute("SELECT * FROM Template").fetchall()
    return render_template("templates_list.html", templates=templates)


@app.route("/templates/<int:template_id>", methods=["GET"])
def template(template_id):
    db = get_db()
    template = db.execute("SELECT * FROM Template where id=?", str(template_id)).fetchone()
    fields = db.execute("SELECT * FROM TemplateField where template_id=?", str(template_id)).fetchall()
    return render_template("template.html", template=template, fields=fields)


@app.route("/", methods=["GET"])
def cms_home():
    return render_template("index.html")
