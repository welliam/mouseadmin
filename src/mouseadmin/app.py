from itertools import groupby
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
from flask import Flask, render_template, request, redirect, g, render_template_string
from bs4 import BeautifulSoup
from typing import Optional
import pathlib
import json
from slugify import slugify
from abc import ABC, abstractmethod

from mouseadmin import neocities, file_client


app = Flask(__name__)

NEOCITIES_DOMAIN = os.getenv("NEOCITIES_DOMAIN", "https://fern.neocities.org")

API_KEY = os.getenv("NEOCITIES_API_KEY")

DATABASE = os.getenv("MOUSEADMIN_DB")


def stars(n):
    n = float(n.strip())
    return int(n) * "★" + ("" if n.is_integer() else "☆")


def by_first_letter(entries, key):
    sorted_entries = sorted(entries, key=lambda entry: entry[key])
    return groupby(sorted_entries, lambda entry: next(filter(str.isalnum, entry["title"])))

TEMPLATE_GLOBALS = {
    "slugify": slugify,
    "stars": stars,
    "NEOCITIES_DOMAIN": NEOCITIES_DOMAIN,
    "len": len,
    "by_first_letter": by_first_letter,
}


def get_client():
    return dict(
        file=file_client.FileClient(), neocities=neocities.NeoCities(api_key=API_KEY)
    )[os.getenv("NEOCITIES_CLIENT", "file")]


def upload_strings(files: dict[str, str]):
    """
    files is a dict {filename: string_content}
    """

    def _temp_file_of(string_content: str):
        review_file = tempfile.NamedTemporaryFile(mode="w")
        review_file.write(string_content)
        review_file.seek(0)
        return review_file

    file_objects = {
        neocities_path: _temp_file_of(string_content)
        for neocities_path, string_content in files.items()
    }
    get_client().upload(
        *((file.name, neocities_path) for neocities_path, file in file_objects.items())
    )


def get_template_variables(template_entry_id):
    db = get_db()
    field_values = db.execute(
        """
        SELECT *
        FROM TemplateFieldValue
        INNER JOIN TemplateEntry ON TemplateFieldValue.template_entry_id=TemplateEntry.id
        INNER JOIN TemplateField ON TemplateFieldValue.template_field_id=TemplateField.id
        WHERE TemplateFieldValue.template_entry_id=?
    """,
        (str(template_entry_id),),
    ).fetchall()

    template = db.execute(
        "SELECT * from Template where id=(select template_id from TemplateEntry where id=?)",
        (str(template_entry_id),)
    ).fetchone()

    parameters = {
        field_value["field_name"]: json.loads(field_value["value_json"])
        for field_value in field_values
    }
    parameters["neocities_path"] = os.path.join(
        template["neocities_path"],
        render_template_string(
            template["entry_path_template"], **TEMPLATE_GLOBALS, **parameters
        ),
    )
    return parameters


def upload_entries(*, template_entry_id=None, template_id=None):
    if template_entry_id is None and template_id is None:
        raise ValueError("Supply one of template_entry_id or template_id")

    db = get_db()
    template_entry_ids = (
        [template_entry_id]
        if template_entry_id is not None
        else [
            row["id"]
            for row in db.execute(
                "SELECT id FROM TemplateEntry WHERE template_id=? ORDER BY timestamp DESC", (str(template_id),)
            ).fetchall()
        ]
    )
    template_id = (
        template_id
        or db.execute(
            "SELECT template_id FROM TemplateEntry where id=?",
            (str(template_entry_id),),
        ).fetchone()["template_id"]
    )

    template = db.execute(
        "SELECT * from Template where id=?", (str(template_id),)
    ).fetchone()

    entries = [get_template_variables(entry_id) for entry_id in template_entry_ids]

    files = {}

    # create entries
    for entry in entries:
        template_parameters = {**TEMPLATE_GLOBALS, **entry}
        filepath = entry["neocities_path"]
        file_contents = render_template_string(
            template["entry_template"], **template_parameters
        )
        files[filepath] = file_contents

    index_path = os.path.join(
        template["neocities_path"],
        "index.html",
    )
    index_html = render_template_string(
        template["index_template"], entries=entries, **TEMPLATE_GLOBALS
    )
    files[index_path] = index_html

    upload_strings(files)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


class InputType(ABC):
    KEY = NotImplemented

    @abstractmethod
    def html(self, field, value):
        pass

    def from_form_value(self, form_value):
        return form_value.strip()

    @classmethod
    def from_field_type(cls, field_type):
        for subclass in cls.__subclasses__():
            if subclass.KEY == field_type:
                return subclass()

        raise ValueError("Unknown field type", field_type)

    @classmethod
    def all(cls):
        return [subclass() for subclass in cls.__subclasses__()]


class TextInput(InputType):
    KEY = "text"

    def html(self, field, value):
        name = field["field_name"]
        return f'<input type="text" name="{name}" value="{value}" />'


class HtmlInput(InputType):
    KEY = "html"

    def html(self, field, value):
        name = field["field_name"]
        return f'<textarea style="height: 500px; width: 70%" type="text" name="{name}">{value}</textarea>'


class CheckboxInput(InputType):
    KEY = "checkbox"

    def html(self, field, value):
        name = field["field_name"]
        checked = "checked" if value else ""
        return f'<input type="checkbox" name="{name}" {checked} />'

    def from_form_value(self, form_value):
        return form_value.strip() == "on"


class SelectInput(InputType):
    KEY = "select"

    def html(self, field, value):
        name = field["field_name"]
        options_html = ""
        for option in json.loads(field["field_options"]):
            selected = "selected" if str(option) == str(value) else ""
            options_html += f'<option value="{option}" {selected}>{option}</option>'

        return f'<select name="{name}">{options_html}</select>'

    def from_form_value(self, form_value):
        return form_value.strip()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@dataclass
class Template:
    name: str
    neocities_path: str
    template_jinja: str
    index_jinja: str


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


def field_options(field):
    if not field["field_options"]:
        return ""
    return ", ".join(json.loads(field["field_options"]))


@app.route("/templates/new", methods=["GET", "POST"])
def new_template():
    if request.method == "GET":
        return render_template(
            "edit_template.html", template=None, input_types=InputType.all()
        )
    else:
        db = get_db()
        template_name = request.form["template_name"]
        neocities_path = request.form["neocities_path"]
        index_template = request.form["index_template"]
        entry_path_template = request.form["entry_path_template"]
        entry_template = request.form["entry_template"]
        cur = db.execute(
            """
            insert into Template(name, neocities_path, entry_path_template, entry_template, index_template)
            values(?, ?, ?, ?, ?)
        """,
            (
                template_name,
                neocities_path,
                entry_path_template,
                entry_template,
                index_template,
            ),
        )
        template_id = cur.lastrowid
        db.executemany(
            """
            insert into TemplateField(template_id, field_name, field_type, field_options)
            values(?, ?, ?, ?)
        """,
            [
                (
                    template_id,
                    field_name,
                    field_type,
                    json.dumps([option.strip() for option in field_options.split(",")]),
                )
                for field_name, field_type, field_options in zip(
                    request.form.getlist("field_name"),
                    request.form.getlist("field_type"),
                    request.form.getlist("field_options"),
                )
                if field_name.strip()
            ],
        )
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
    cur = db.execute(
        """
           UPDATE Template
           SET name=?, neocities_path=?, entry_path_template=?, entry_template=?, index_template=?
           WHERE id=?
    """,
        (
            template_name,
            neocities_path,
            entry_path_template,
            entry_template,
            index_template,
            template_id,
        ),
    )
    db.execute("delete from TemplateField where template_id=?", template_id)
    db.executemany(
        """
           insert into TemplateField(template_id, field_name, field_type, field_options)
           values(?, ?, ?, ?)
       """,
        [
            (
                template_id,
                field_name,
                field_type,
                json.dumps([option.strip() for option in field_options.split(",")]),
            )
            for field_name, field_type, field_options in zip(
                request.form.getlist("field_name"),
                request.form.getlist("field_type"),
                request.form.getlist("field_options"),
            )
            if field_name.strip()
        ],
    )
    db.commit()
    upload_entries(template_id=template_id)
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


@app.route("/templates/<int:template_id>/edit", methods=["GET"])
def template_edit(template_id):
    db = get_db()
    template = db.execute(
        "SELECT * FROM Template where id=?", (str(template_id),)
    ).fetchone()
    fields = db.execute(
        "SELECT * FROM TemplateField where template_id=?", (str(template_id),)
    ).fetchall()
    return render_template(
        "edit_template.html",
        template=template,
        fields=fields,
        field_options=field_options,
        input_types=InputType.all(),
    )


def render_entry(template_entry_id):
    db = get_db()
    entry = db.execute(
        "SELECT * FROM TemplateEntry where id=?", (str(template_entry_id),)
    ).fetchone()
    template = db.execute(
        "SELECT * FROM Template where id=?", (str(entry["template_id"]),)
    ).fetchone()
    template_variables = get_template_variables(template_entry_id)
    entry_path = render_template_string(
        template["entry_path_template"], **TEMPLATE_GLOBALS, **template_variables
    )
    entry_html = render_template_string(
        template["entry_template"], **TEMPLATE_GLOBALS, **template_variables
    )
    return dict(entry_path=entry_path, entry_html=entry_html)


@app.route("/templates/<int:template_id>", methods=["GET"])
def template(template_id):
    db = get_db()
    template = db.execute(
        "SELECT * FROM Template where id=?", str(template_id)
    ).fetchone()
    fields = db.execute(
        "SELECT * FROM TemplateField where template_id=?", str(template_id)
    ).fetchall()
    template_entries = db.execute(
        "SELECT * FROM TemplateEntry where template_id=?", str(template_id)
    ).fetchall()
    return render_template(
        "template.html",
        template=template,
        fields=fields,
        template_entries=[
            dict(entry, **render_entry(entry["id"])) for entry in template_entries
        ],
    )


def field_html(field, value=None):
    input_html = InputType.from_field_type(field["field_type"]).html(field, value or "")
    return f"""
        <li>
            <label for="{field['field_name']}">{field['field_name']}</label>
            {input_html}
        </li>
    """


@app.route("/templates/<int:template_id>/entry/new", methods=["GET", "POST"])
def new_template_entry(template_id):
    db = get_db()
    if request.method == "GET":
        template = db.execute(
            "SELECT * FROM Template where id=?", str(template_id)
        ).fetchone()
        fields = db.execute(
            "SELECT * FROM TemplateField where template_id=?", str(template_id)
        ).fetchall()
        fields_html = [field_html(field) for field in fields]
        return render_template(
            "edit_entry.html", template=template, fields=fields, fields_html=fields_html
        )
    if request.method == "POST":
        template = db.execute(
            "SELECT * FROM Template where id=?", str(template_id)
        ).fetchone()
        fields = db.execute(
            "SELECT * FROM TemplateField where template_id=?", str(template_id)
        ).fetchall()
        field_by_name = {field["field_name"]: field for field in fields}
        template_entry_id = db.execute(
            """
            INSERT INTO TemplateEntry(last_updated, template_id) values (?, ?)
        """,
            (datetime.now(), str(template_id)),
        ).lastrowid
        db.executemany(
            """
            insert into TemplateFieldValue(template_entry_id, template_field_id, value_json)
            values(?, ?, ?)
        """,
            [
                (
                    template_entry_id,
                    field_by_name[field_name]["id"],
                    json.dumps(
                        InputType.from_field_type(
                            field_by_name[field_name]["field_type"]
                        ).from_form_value(field_value)
                    ),
                )
                for field_name, field_value in request.form.items()
            ],
        )
        db.commit()
        upload_entries(template_entry_id=template_entry_id)
        return redirect(f"/templates/{template_id}")


@app.route(
    "/templates/<int:template_id>/entry/<int:template_entry_id>",
    methods=["GET", "POST"],
)
def update_template_entry(template_id, template_entry_id):
    db = get_db()
    if request.method == "GET":
        template = db.execute(
            "SELECT * FROM Template where id=?", str(template_id)
        ).fetchone()
        fields = db.execute(
            "SELECT * FROM TemplateField where template_id=?", str(template_id)
        ).fetchall()
        template_variables = get_template_variables(template_entry_id)
        fields_html = [
            field_html(field, template_variables.get(field["field_name"], None))
            for field in fields
        ]
        return render_template(
            "edit_entry.html", template=template, fields=fields, fields_html=fields_html
        )
    if request.method == "POST":
        fields = db.execute(
            "SELECT * FROM TemplateField where template_id=?", str(template_id)
        ).fetchall()
        field_by_name = {field["field_name"]: field for field in fields}
        db.execute(
            "DELETE FROM TemplateFieldValue where template_entry_id=?",
            str(template_entry_id),
        )
        db.executemany(
            """
            insert into TemplateFieldValue(template_entry_id, template_field_id, value_json)
            values(?, ?, ?)
        """,
            [
                (
                    template_entry_id,
                    field_by_name[field_name]["id"],
                    json.dumps(
                        InputType.from_field_type(
                            field_by_name[field_name]["field_type"]
                        ).from_form_value(field_value)
                    ),
                )
                for field_name, field_value in request.form.items()
            ],
        )
        db.commit()
        upload_entries(template_entry_id=template_entry_id)
        return redirect(f"/templates/{template_id}")


@app.route("/templates/<int:template_id>/entry/preview", methods=["POST"])
def preview_template(template_id):
    db = get_db()
    template = db.execute(
        "SELECT * FROM Template where id=?", str(template_id)
    ).fetchone()
    return render_template_string(
        template["entry_template"], **TEMPLATE_GLOBALS, **request.form
    )


@app.route("/", methods=["GET"])
def cms_home():
    return render_template("index.html")
