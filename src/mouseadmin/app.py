import re
from dataclasses import dataclass
from datetime import datetime
import os
from flask import Flask, render_template

from mouseadmin import neocities


app = Flask(__name__)


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
