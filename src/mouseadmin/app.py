import re
from dataclasses import dataclass
from datetime import datetime
import os
from flask import Flask, render_template

from mouseadmin import neocities


app = Flask(__name__)


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
            extra_content_html=self.extra_content_html,
            rating_stars="*" * self.stars + "." if self.rating - int(self.rating) else "",
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
            if "reviews/" in item["path"] and not item["is_directory"]
        ]
        return sorted(reviews, key=lambda review: review.date)

    @property
    def date(self):
        [datestr] = re.match("reviews/([0-9]+-[0-9]+-[0-9]+)", self.path).groups()
        return datetime.fromisoformat(datestr).date()


def fetch_reviews(client) -> list[ReviewInfo]:
    items = client.listitems()["files"]
    return ReviewInfo.parse_reviews(items)


@app.route("/reviews")
def reviews():
    client = neocities.NeoCities(api_key=os.getenv("MOUSEADMIN_SITE_API_KEY"))
    return render_template("review_list.html", items=fetch_reviews(client))
