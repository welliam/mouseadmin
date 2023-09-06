import tempfile
from slugify import slugify
from decimal import Decimal
import re
from dataclasses import dataclass
from datetime import datetime, date
import os
from flask import Flask, render_template, request, redirect

from mouseadmin import neocities


app = Flask(__name__)


REVIEW_NEOCITIES_PATH = "reviews/"

REVIEW_HOME_NEOCITIES_PATH = REVIEW_NEOCITIES_PATH + "home.html"


class MouseadminNeocitiesClient:
    _client: neocities.NeoCities

    def __init__(self):
        self._client = neocities.NeoCities(
            api_key=os.getenv("MOUSEADMIN_SITE_API_KEY")
        )

    def listitems(self):
        return self._client.listitems()

    def _temp_file_of(self, string_content: str):
        review_file = tempfile.NamedTemporaryFile(mode="w")
        review_file.write(string_content)
        review_file.seek(0)
        return review_file

    def upload_strings(self, files: dict[str, str]):
        """
        files is a dict {filename: string_content}
        """
        file_objects = {
            neocities_path: self._temp_file_of(string_content)
            for neocities_path, string_content in files.items()
        }
        self._client.upload(*(
            (file.name, neocities_path)
            for neocities_path, file in file_objects.items()
        ))



@dataclass
class FullReview:
    path: str
    title: str
    developer: str
    rating: Decimal
    platform: str
    completion: str
    method: str
    date: date
    art_url: str
    review_html: str
    recommendation_html: str
    extra_content_html: str

    @classmethod
    def empty(cls):
        return cls(
            path="",
            title="",
            developer="",
            rating=3,
            platform="",
            completion="",
            method="",
            date=date.today(),
            art_url="",
            review_html="",
            recommendation_html="",
            extra_content_html="",
        )

    @classmethod
    def new(cls, date: date, title: str, **kwargs):
        path = f"{str(date)}-{slugify(title)}"
        return cls(
            path=path,
            date=date,
            title=title,
            **kwargs,
        )

    def neocities_path(self) -> str:
        return REVIEW_NEOCITIES_PATH + self.path + ".html"

    def review_template_context(self) -> dict:
        return dict(
            path=self.path,
            title=self.title,
            developer=self.developer,
            rating=self.rating,
            platform=self.platform,
            completion=self.completion,
            method=self.method,
            date_iso=str(self.date),
            date_string=self.date.strftime("%b %d, %Y"),
            art_url=self.art_url,
            review_html=self.review_html,
            recommendation_html=self.recommendation_html,
            extra_content_html=self.extra_content_html.strip(),
            rating_stars=("★" * int(self.rating) + ("☆" if self.rating - int(self.rating) else "")) if self.rating else "",
        )


@dataclass
class ReviewInfo:
    is_directory: bool
    path: str
    sha1_hash: str
    size: int
    updated_at: str

    @classmethod
    def parse_reviews(cls, items) -> list["ReviewInfo"]:
        reviews = [
            ReviewInfo(**item)
            for item in items
            if REVIEW_NEOCITIES_PATH in item["path"]
            and not item["is_directory"]
        ]
        return sorted(reviews, key=lambda review: review.date, reverse=True)

    @property
    def date(self):
        [datestr] = re.match("reviews/([0-9]+-[0-9]+-[0-9]+)", self.path).groups()
        return datetime.fromisoformat(datestr).date()


def fetch_reviews(client) -> list[ReviewInfo]:
    items = client.listitems()["files"]
    return ReviewInfo.parse_reviews(items)


@app.route("/reviews/")
def reviews():
    client = neocities.NeoCities(api_key=os.getenv("MOUSEADMIN_SITE_API_KEY"))
    return render_template("review_list.html", items=fetch_reviews(client))


@app.route("/reviews/preview/", methods=["POST"])
def preview_edit():
    kwargs = dict(
        request.form,
        date=datetime.fromisoformat(request.form['date']).date(),
        rating=Decimal(request.form['rating']),
    )
    review = FullReview.new(**kwargs)
    return render_template(
        "review.html",
        **review.review_template_context(),
    )


@app.route("/reviews/new/", methods=["GET", "POST"])
def new_edit():
    if request.method == "GET":
        return render_template(
            "review_edit.html",
            **FullReview.empty().review_template_context(),
        )
    else:
        client = MouseadminNeocitiesClient()
        kwargs = dict(
            request.form,
            date=datetime.fromisoformat(request.form['date']).date(),
            rating=Decimal(request.form['rating']),
        )
        review = FullReview.new(**kwargs)
        rendered_template = render_template(
            "review.html",
            **review.review_template_context(),
        )
        client.upload_strings({review.neocities_path(): rendered_template})
        return redirect("/reviews")
