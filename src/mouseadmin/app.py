import requests
import tempfile
from slugify import slugify
from decimal import Decimal
import re
from dataclasses import dataclass
from datetime import datetime, date
import os
from flask import Flask, render_template, request, redirect
from bs4 import BeautifulSoup
from typing import Optional

from mouseadmin import neocities


app = Flask(__name__)


REVIEW_NEOCITIES_PATH = "reviews/"

REVIEW_HOME_NEOCITIES_PATH = REVIEW_NEOCITIES_PATH + "home.html"

NEOCITIES_DOMAIN = os.getenv("NEOCITIES_DOMAIN", "https://fern.neocities.org")

API_KEY = os.getenv("MOUSEADMIN_SITE_API_KEY")


class MouseadminNeocitiesClient:
    _client: neocities.NeoCities

    def __init__(self):
        self._client = neocities.NeoCities(
            api_key=API_KEY,
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
    date: Optional[date]
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
            date=None,
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

    @staticmethod
    def _parse_html(soup: BeautifulSoup, id: str) -> str:
        content = soup.find(id=id)
        return content.encode_contents().decode().strip()

    @classmethod
    def parse_review(cls, path: str, review_html: str):
        soup = BeautifulSoup(review_html, features="html.parser")
        house = soup.find(id="game-house")
        print(cls._parse_html(soup, "game-review-content"))
        return cls(
            path=path,
            title=house["data-title"],
            developer=house["data-developer"],
            rating=Decimal(house["data-rating"]),
            platform=house["data-platform"],
            completion=house["data-completion"],
            method=house["data-method"],
            date=datetime.fromisoformat(house["data-date"]).date(),
            art_url=house["data-art-url"],
            review_html=cls._parse_html(soup, "game-review-content"),
            recommendation_html=cls._parse_html(soup, "game-rec-answer"),
            extra_content_html=cls._parse_html(soup, "extras"),
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
            date_iso=str(self.date) if self.date else None,
            date_string=self.date.strftime("%Y %b %-d").lower() if self.date else None,
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

    @property
    def slug(self):
        [slug] = re.match(r"reviews/([0-9]+-[0-9]+-[0-9]+-[^\.]+)\.html", self.path).groups()
        return slug


def fetch_reviews(client) -> list[ReviewInfo]:
    items = client.listitems()["files"]
    return ReviewInfo.parse_reviews(items)


def fetch_full_review_from_slug(slug: str) -> FullReview:
    url = f"{NEOCITIES_DOMAIN}/reviews/{slug}.html"
    return FullReview.parse_review(slug, requests.get(url).text)


@app.route("/review/")
def review():
    client = MouseadminNeocitiesClient()
    return render_template(
        "review_list.html",
        items=fetch_reviews(client),
        NEOCITIES_DOMAIN=NEOCITIES_DOMAIN,
    )


@app.route("/review/preview/", methods=["POST"])
def preview_review():
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


@app.route("/review/new/", methods=["GET", "POST"])
def new_review():
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
        return redirect("/review")


@app.route("/review/edit/<path>", methods=["GET", "POST"])
def edit_review(path):
    if request.method == "GET":
        return render_template(
            "review_edit.html",
            **fetch_full_review_from_slug(path).review_template_context(),
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
        return redirect("/review")
