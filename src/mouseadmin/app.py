from urllib.parse import unquote
import hashlib
import math
from PIL import Image
import io
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
from time import sleep
import logging
from flask_caching import Cache


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


from mouseadmin import neocities, file_client


app = Flask(__name__)
app.config["SECRET_KEY"] = "jsdfao987jwer8xo3ru1m3rum89yem89f"
app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 15  # timeout in seconds
cache = Cache(app)

NEOCITIES_DOMAIN = os.getenv("NEOCITIES_DOMAIN", "https://fern.neocities.org")

API_KEY = os.getenv("NEOCITIES_API_KEY")

DATABASE = os.getenv("MOUSEADMIN_DB")


month_list = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "june",
    "july",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


@cache.cached(timeout=15)
def listitems():
    client = get_client()
    return client.listitems()


def get_neocities_file(remote_filename):
    """
    Get a file, checking if it has changed based on its SHA1 hash.

    Parameters
    ----------
    remote_filename : str
        The name of the file on the server.
    local_cache_path : str
        The path to the locally cached file.

    Returns
    -------
    file_bytes : bytes
        The content of the file.
    """
    client = get_client()
    pathname = unquote(remote_filename.split(NEOCITIES_DOMAIN)[1])
    local_cache_path = os.path.join("cache", pathname.strip("/"))
    # Fetch file list and its SHA1 hash from server
    files_info = listitems()
    file_data = next(
        (
            file
            for file in files_info.get("files", [])
            if file["path"] == pathname.strip("/")
        ),
        None,
    )

    if not file_data:
        raise FileNotFoundError(f"File '{pathname}' not found on server.")

    remote_hash = file_data["sha1_hash"]

    # Check local cache
    if os.path.exists(local_cache_path):
        with open(local_cache_path, "rb") as f:
            local_bytes = f.read()
            local_hash = hashlib.sha1(local_bytes).hexdigest()

        # If hashes match, return cached version
        if local_hash == remote_hash:
            return local_bytes

    # If no match, download the file
    response = requests.get(remote_filename)
    if response.status_code != 200:
        raise Exception(
            f"Failed to download file: {response.status_code} {response.reason}"
        )

    file_bytes = response.content

    os.makedirs(os.path.dirname(local_cache_path), exist_ok=True)

    # Update cache
    with open(local_cache_path, "wb") as f:
        f.write(file_bytes)

    return file_bytes


def json_dumps(x):
    return json.dumps(x, sort_keys=True, default=str)


def json_loads(x):
    if x:
        return json.loads(x)
    return None


@app.template_filter("sorted")
def sorted_desc(args):
    iterable, attr = args
    return sorted(iterable, key=lambda x: x[attr] or "", reverse=True)


def stars(n):
    n = float(n.strip())
    return int(n) * "★" + ("" if n.is_integer() else "☆")


def by_first_letter(entries, key):
    def get_title(entry):
        return "".join(filter(str.isalnum, entry["title"].upper()))

    sorted_entries = sorted(entries, key=get_title)
    return groupby(sorted_entries, lambda entry: next(iter(get_title(entry))))


def month_of(datestring):
    if datestring:
        return date.fromisoformat(datestring).month
    return None


def year_of(datestring):
    if datestring:
        return date.fromisoformat(datestring).year
    return None


def month_to_name(n):
    if n:
        return month_list[int(n) - 1]
    return None


def key(t):
    return lambda x: x[t]


def date_to_string(datestring):
    if datestring:
        d = date.fromisoformat(datestring)
        return f"{d.year} {month_list[d.month - 1]} {d.day}"
    return ""


def thumbnail(image_url):
    _, art_url = image_url.split("/img/")
    return os.path.join("/img/THUMB", art_url)


TEMPLATE_GLOBALS = {
    "slugify": slugify,
    "stars": stars,
    "NEOCITIES_DOMAIN": NEOCITIES_DOMAIN,
    "len": len,
    "by_first_letter": by_first_letter,
    "month_to_name": month_to_name,
    "sorted": sorted,
    "key": key,
    "month_of": month_of,
    "year_of": year_of,
    "date_to_string": date_to_string,
    "thumbnail": thumbnail,
    "json": json,
}


def get_client():
    return dict(
        file=file_client.FileClient(), neocities=neocities.NeoCities(api_key=API_KEY)
    )[os.getenv("NEOCITIES_CLIENT", "file")]


def chunkify(files: list, chunk_size: int):
    for chunk_i in range(math.ceil(len(files) / chunk_size)):
        yield files[chunk_i * chunk_size : (chunk_i + 1) * chunk_size]


def upload_strings(files: dict[str, bytes | str]):
    """
    files is a dict {filename: content}
    """

    CHUNK_SIZE = 25

    def _temp_file_of(content: str | bytes):
        if type(content) == str:
            review_file = tempfile.NamedTemporaryFile(mode="w")
        else:
            review_file = tempfile.NamedTemporaryFile(mode="wb")

        review_file.write(content)
        review_file.seek(0)
        return review_file

    file_objects = {
        neocities_path: _temp_file_of(content)
        for neocities_path, content in files.items()
    }
    file_list = [
        (file.name, neocities_path) for neocities_path, file in file_objects.items()
    ]

    client = get_client()
    looped = False
    for index, chunk in enumerate(chunkify(list(file_list), CHUNK_SIZE)):
        logging.info(f"Uploading chunk of size {len(chunk)}")
        client.upload(*chunk)
        if index != 0:
            sleep(3)


def get_template_variables(template_entry_id):
    db = get_db()
    field_values = db.execute(
        """
        SELECT *
        FROM TemplateFieldValue
        INNER JOIN TemplateEntry ON TemplateFieldValue.template_entry_id=TemplateEntry.id
        INNER JOIN TemplateField ON TemplateFieldValue.template_field_name=TemplateField.field_name
        WHERE TemplateFieldValue.template_entry_id=?
    """,
        (str(template_entry_id),),
    ).fetchall()

    template = db.execute(
        "SELECT * from Template where id=(select template_id from TemplateEntry where id=?)",
        (str(template_entry_id),),
    ).fetchone()

    parameters = {
        field_value["field_name"]: json_loads(field_value["value_json"])
        for field_value in field_values
    }
    parameters["neocities_path"] = os.path.join(
        template["neocities_path"],
        render_template_string(
            template["entry_path_template"], **TEMPLATE_GLOBALS, **parameters
        ),
    )
    return parameters


def regenerate_index(template_id):
    db = get_db()

    template = db.execute(
        "SELECT * from Template where id=?", (str(template_id),)
    ).fetchone()

    template_entry_ids = [
        row["id"]
        for row in db.execute(
            "SELECT id FROM TemplateEntry WHERE template_id=? ORDER BY timestamp DESC",
            (str(template_id),),
        ).fetchall()
    ]
    entries = [get_template_variables(entry_id) for entry_id in template_entry_ids]
    index_path = os.path.join(
        template["neocities_path"],
        "index.html",
    )
    index_html = render_template_string(
        template["index_template"], entries=entries, **TEMPLATE_GLOBALS
    )

    upload_strings({index_path: index_html})


def upload_entries(*, template_entry_id=None, template_id=None):
    if template_entry_id is None and template_id is None:
        raise ValueError("Supply one of template_entry_id or template_id")

    db = get_db()

    template_id = (
        template_id
        or db.execute(
            "SELECT template_id FROM TemplateEntry where id=?",
            (str(template_entry_id),),
        ).fetchone()["template_id"]
    )

    template_entry_ids = [
        row["id"]
        for row in db.execute(
            "SELECT id FROM TemplateEntry WHERE template_id=? ORDER BY timestamp DESC",
            (str(template_id),),
        ).fetchall()
    ]

    template_fields = db.execute(
        "SELECT * FROM TemplateField where template_id=?", (str(template_id),)
    )
    inputs_by_field_name = {
        template_field["field_name"]: InputType.from_field_type(
            template_field["field_type"]
        )
        for template_field in template_fields
    }

    template = db.execute(
        "SELECT * from Template where id=?", (str(template_id),)
    ).fetchone()

    entries = [get_template_variables(entry_id) for entry_id in template_entry_ids]

    files = {}

    # create entries
    for _, entry in filter(
        lambda entry: (
            str(entry[0]) == str(template_entry_id) if template_entry_id else True
        ),
        zip(template_entry_ids, entries),
    ):
        template_parameters = {**TEMPLATE_GLOBALS, **entry}
        filepath = entry["neocities_path"]
        file_contents = render_template_string(
            template["entry_template"], **template_parameters
        )

        # create extra files
        for field_name, field_value in entry.items():
            if field_name in inputs_by_field_name:
                files |= inputs_by_field_name[field_name].extra_files(field_value)

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
    def input_html(self, field, value):
        pass

    def html(self, field, value):
        return (
            f'<span data-input-type="{self.KEY}">{self.input_html(field, value)}</span>'
        )

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

    def extra_files(self, value):
        # extra files to generate from form value on save
        return {}


class TextInput(InputType):
    KEY = "text"

    def input_html(self, field, value):
        name = field["field_name"]
        return f'<input type="text" name="{name}" value="{value}" />'


class ImageURLInput(InputType):
    KEY = "image_url"

    def input_html(self, field, value):
        name = field["field_name"]
        return f'<input type="text" name="{name}" value="{value}" /> <img class="image-preview" style="display: none">'

    def extra_files(self, image_url):
        thumbnail_max_height_px = 250
        thumbnail_max_width_px = 250

        try:
            if image_url.startswith(NEOCITIES_DOMAIN):
                result = get_neocities_file(image_url)
            else:
                http_result = requests.get(image_url)
                http_result.raise_for_status()
                result = http_result.content
        except requests.exceptions.ConnectionError:
            return {}

        image = Image.open(io.BytesIO(result))
        image.thumbnail((thumbnail_max_height_px, thumbnail_max_width_px))
        image_bytes_io = io.BytesIO()
        image.save(image_bytes_io, format="png")
        image_bytes = image_bytes_io.getvalue()

        return {thumbnail(image_url): image_bytes}


class HtmlInput(InputType):
    KEY = "html"

    def input_html(self, field, value):
        name = field["field_name"]
        return f'<textarea style="height: 500px; width: 70%" type="text" name="{name}">{value}</textarea>'


class CheckboxInput(InputType):
    KEY = "checkbox"

    def input_html(self, field, value):
        name = field["field_name"]
        checked = "checked" if value else ""
        return f'<input type="checkbox" name="{name}" {checked} />'

    def from_form_value(self, form_value):
        return form_value.strip() == "on"


class SelectInput(InputType):
    KEY = "select"

    def input_html(self, field, value):
        name = field["field_name"]
        options_html = ""
        for option in json_loads(field["field_options"]):
            selected = "selected" if str(option) == str(value) else ""
            options_html += f'<option value="{option}" {selected}>{option}</option>'

        return f'<select name="{name}">{options_html}</select>'

    def from_form_value(self, form_value):
        return form_value.strip()


class DateInput(InputType):
    KEY = "date"

    def input_html(self, field, value):
        name = field["field_name"]
        # Set a default value or use the provided one
        value = value or ""
        return f'<input type="date" name="{name}" value="{value}">'

    def from_form_value(self, form_value):
        try:
            # Parse the form value into a Python date object
            return datetime.strptime(form_value.strip(), "%Y-%m-%d").date()
        except ValueError:
            # Handle invalid date formats gracefully
            return None


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
    return ", ".join(json_loads(field["field_options"]))


@app.route("/templates/new", methods=["GET", "POST"])
def new_template():
    if request.method == "GET":
        return render_template(
            "edit_template.html", template=None, input_types=InputType.all()
        )
    else:
        db = get_db()
        template_name = request.form["template_name"]

        if template_name in [
            template["name"]
            for template in db.execute("select name from Template").fetchall()
        ]:
            return "Duplicate template name not allowed", 400

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
                    json_dumps([option.strip() for option in field_options.split(",")]),
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

    if template_name in [
        template["name"]
        for template in db.execute(
            "select name from Template where id != ?", (template_id,)
        ).fetchall()
    ]:
        return "Duplicate template name not allowed", 400

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
                json_dumps([option.strip() for option in field_options.split(",")]),
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
    return dict(
        entry_path=entry_path,
        entry_html=entry_html,
        template_variables=template_variables,
    )


def entry_path_exists(*, db, template_id, form, template_entry_id=None):
    template = db.execute(
        "SELECT * FROM Template where id=?", (str(template_id),)
    ).fetchone()
    path = render_template_string(
        template["entry_path_template"], **TEMPLATE_GLOBALS, **form
    )
    template_entry_ids = map(
        lambda x: x["id"],
        db.execute(
            "select id from TemplateEntry where template_id = ? and id != ?",
            (str(template_id), str(template_entry_id)),
        ),
    )
    return path in (
        render_entry(template_entry_id)["entry_path"]
        for template_entry_id in template_entry_ids
    )


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
        "SELECT * FROM TemplateEntry where template_id=? ORDER BY timestamp DESC",
        str(template_id),
    ).fetchall()
    return render_template(
        "template.html",
        **TEMPLATE_GLOBALS,
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

        if entry_path_exists(db=db, template_id=template_id, form=request.form):
            return "A template entry with this name already exists", 400

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
            insert into TemplateFieldValue(template_entry_id, template_field_name, value_json)
            values(?, ?, ?)
        """,
            [
                (
                    template_entry_id,
                    field_by_name[field_name]["field_name"],
                    json_dumps(
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
        if entry_path_exists(
            db=db,
            template_id=template_id,
            form=request.form,
            template_entry_id=template_entry_id,
        ):
            return "A template entry with this name already exists", 400

        fields = db.execute(
            "SELECT * FROM TemplateField where template_id=?", str(template_id)
        ).fetchall()
        field_by_name = {field["field_name"]: field for field in fields}
        db.execute(
            "DELETE FROM TemplateFieldValue where template_entry_id=?",
            (str(template_entry_id),),
        )
        db.executemany(
            """
            insert into TemplateFieldValue(template_entry_id, template_field_name, value_json)
            values(?, ?, ?)
            """,
            [
                (
                    template_entry_id,
                    field_by_name[field_name]["field_name"],
                    json_dumps(
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
    "/templates/entry/<int:template_entry_id>/delete",
    methods=["POST"],
)
def delete_template_entry(template_entry_id):
    db = get_db()
    template_entry = db.execute(
        "select * from TemplateEntry where id=?", [str(template_entry_id)]
    ).fetchone()
    db.execute(
        "DELETE FROM TemplateFieldValue where template_entry_id=?",
        [str(template_entry_id)],
    )
    db.execute("DELETE FROM TemplateEntry where id=?", [str(template_entry_id)])
    db.commit()
    regenerate_index(template_entry["template_id"])
    return "Done", 201


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
