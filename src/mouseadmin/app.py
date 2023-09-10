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
from flask import Flask, render_template, request, redirect
from bs4 import BeautifulSoup
from typing import Optional
import pathlib

from mouseadmin import neocities


app = Flask(__name__)


NEOCITIES_PATH_REVIEW = "reviews/"

NEOCITIES_PATH_REVIEW_HOME = NEOCITIES_PATH_REVIEW + "home.html"

NEOCITIES_DOMAIN = os.getenv("NEOCITIES_DOMAIN", "https://fern.neocities.org")

API_KEY = os.getenv("MOUSEADMIN_SITE_API_KEY")


@dataclass
class FullReview:
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

    @property
    def slug(self):
        return slugify(self.title)

    @classmethod
    def new(cls, date: date, title: str, **kwargs):
        return cls(
            date=date,
            title=title,
            **kwargs,
        )

    @staticmethod
    def _parse_html(soup: BeautifulSoup, id: str) -> str:
        content = soup.find(id=id)
        if content is None:
            return ""
        return content.encode_contents().decode().strip()

    @classmethod
    def parse_review(cls, review_html: str):
        soup = BeautifulSoup(review_html, features="html.parser")
        house = soup.find(id="game-house")
        return cls(
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

    @property
    def neocities_path(self) -> str:
        return "/" + NEOCITIES_PATH_REVIEW + self.slug + ".html"

    def formatted_date(self):
        if not self.date:
            return None
        formatted = self.date.strftime("%Y %b %-d").lower()
        for abbrev, full in [
            ("mar", "march"),
            ("apr", "april"),
            ("may", "may"),
            ("jun", "june"),
            ("jul", "july"),
            ("sep", "sept"),
        ]:
            formatted = formatted.replace(abbrev, full)
        return formatted

    def review_template_context(self) -> dict:
        return dict(
            slug=self.slug,
            title=self.title,
            developer=self.developer,
            neocities_path=self.neocities_path,
            rating=self.rating,
            platform=self.platform,
            completion=self.completion,
            method=self.method,
            date_iso=str(self.date) if self.date else None,
            date_string=self.formatted_date(),
            art_url=self.art_url,
            review_html=self.review_html,
            recommendation_html=self.recommendation_html,
            extra_content_html=self.extra_content_html.strip(),
            rating_stars=(
                "★" * int(self.rating) + ("☆" if self.rating - int(self.rating) else "")
            )
            if self.rating
            else "",
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
            if item["path"].startswith(NEOCITIES_PATH_REVIEW)
            and not item["is_directory"]
            and not "home.html" in item["path"]
        ]
        return reviews

    @property
    def updated_at_datetime(self) -> datetime:
        return parser.parse(self.updated_at)

    @property
    def slug(self):
        [slug] = re.match(
            f"{NEOCITIES_PATH_REVIEW}([^\\.]+)\\.html", self.path
        ).groups()
        return slug


class MouseadminNeocitiesClient:
    _client: neocities.NeoCities

    def __init__(self):
        self._client = neocities.NeoCities(
            api_key=API_KEY,
        )

    @cached_property
    def items(self):
        print("LISTITEMS")
        return self._client.listitems()

    def _get_full_review(self, path):
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

    def get_full_review(self, path) -> FullReview:
        _, result = self._get_full_review(path)
        return FullReview.parse_review(result)

    def list_full_reviews(self) -> list[FullReview]:
        pages: list[FullReview] = []
        has_fetched = False
        for review in self.fetch_reviews_info():
            fetched, content = self._get_full_review(review.path)
            pages.append(FullReview.parse_review(content))
            if fetched and has_fetched:
                print("THROTTLING FETCHES")
                time.sleep(10)
            has_fetched = has_fetched or fetched
        return sorted(pages, key=lambda page: page.date, reverse=True)

    def fetch_reviews_info(self) -> list["ReviewInfo"]:
        items = self.items["files"]
        return ReviewInfo.parse_reviews(items)

    def _temp_file_of(self, string_content: str):
        review_file = tempfile.NamedTemporaryFile(mode="w")
        review_file.write(string_content)
        review_file.seek(0)
        return review_file

    def upload_strings(self, files: dict[str, str]):
        """
        files is a dict {filename: string_content}
        """
        review_infos = self.fetch_reviews_info()
        if review_infos:
            newest_review_updated_at = max(
                review.updated_at_datetime for review in review_infos
            )
            seconds_to_sleep = (
                timedelta(minutes=1.1)
                - (datetime.now(timezone.utc) - newest_review_updated_at)
            ).total_seconds()
            if seconds_to_sleep > 0:
                print(f"THROTTLING WRITES {seconds_to_sleep} seconds")
                time.sleep(seconds_to_sleep)

        file_objects = {
            neocities_path: self._temp_file_of(string_content)
            for neocities_path, string_content in files.items()
        }
        self._client.upload(
            *(
                (file.name, neocities_path)
                for neocities_path, file in file_objects.items()
            )
        )
        for path, contents in files.items():
            open(f"cache/{path}", "w").write(contents)

    def fetch_full_review_from_slug(self, slug: str) -> FullReview:
        path = f"/{NEOCITIES_PATH_REVIEW}{slug}.html"
        return self.get_full_review(path)

    def fetch_home_context(self, reviews: list[FullReview]) -> dict:
        # reviews = self.list_full_reviews()
        most_recent_review = reviews[0]
        recent_reviews = reviews[1:3]
        reviews_by_first_letter = [
            (
                letter,
                [
                    review.review_template_context()
                    for review in sorted(reviews, key=lambda review: review.title)
                    if review.title.lower().startswith(letter.lower())
                ],
            )
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ]
        reviews_by_first_letter = [
            (letter, reviews) for letter, reviews in reviews_by_first_letter if reviews
        ]
        return dict(
            game_review_count=len(reviews),
            reviews_by_first_letter=reviews_by_first_letter,
            most_recent_review=most_recent_review.review_template_context(),
            recent_reviews=recent_reviews,
            NEOCITIES_DOMAIN=NEOCITIES_DOMAIN,
        )


@app.route("/review/")
def review():
    client = MouseadminNeocitiesClient()
    return render_template(
        "review_list.html",
        items=[
            review.review_template_context() for review in client.list_full_reviews()
        ],
        NEOCITIES_DOMAIN=NEOCITIES_DOMAIN,
    )


@app.route("/review/preview/", methods=["POST"])
def preview_review():
    kwargs = dict(
        request.form,
        date=datetime.fromisoformat(request.form["date"]).date(),
        rating=Decimal(request.form["rating"]),
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
            date=datetime.fromisoformat(request.form["date"]).date(),
            rating=Decimal(request.form["rating"]),
        )
        review = FullReview.new(**kwargs)
        existing_reviews = client.list_full_reviews()
        assert review.slug not in [
            existing_review.slug for existing_review in existing_reviews
        ], "Review already exists! Not saving"

        rendered_template = render_template(
            "review.html",
            **review.review_template_context(),
        )
        reviews = sorted(
            [review, *client.list_full_reviews()],
            key=lambda review: review.date,
            reverse=True,
        )
        client.upload_strings(
            {
                review.neocities_path: rendered_template,
                NEOCITIES_PATH_REVIEW_HOME: render_template(
                    "home.html",
                    **client.fetch_home_context(reviews),
                ),
            }
        )
        return redirect("/review")


@app.route("/review/edit/<slug>", methods=["GET", "POST"])
def edit_review(slug):
    client = MouseadminNeocitiesClient()
    if request.method == "GET":
        return render_template(
            "review_edit.html",
            **client.fetch_full_review_from_slug(slug).review_template_context(),
        )
    else:
        kwargs = dict(
            request.form,
            date=datetime.fromisoformat(request.form["date"]).date(),
            rating=Decimal(request.form["rating"]),
        )
        review = FullReview.new(**kwargs)
        rendered_template = render_template(
            "review.html",
            **review.review_template_context(),
        )
        reviews = sorted(
            [
                (old_review if old_review.slug != slug else review)
                for old_review in client.list_full_reviews()
            ],
            key=lambda review: review.date,
            reverse=True,
        )
        client.upload_strings(
            {
                review.neocities_path: rendered_template,
                NEOCITIES_PATH_REVIEW_HOME: render_template(
                    "home.html", **client.fetch_home_context(reviews)
                ),
            }
        )
        return redirect("/review")


@app.route("/review/home", methods=["GET"])
def home_preview():
    client = MouseadminNeocitiesClient()
    most_recent = self.list_full_reviews()[0]
    return render_template(
        "home.html", **client.fetch_home_context(self.list_full_reviews())
    )
