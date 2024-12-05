from datetime import date
import os
import json
import sqlite3


DATABASE = os.getenv("MOUSEADMIN_DB")
db = sqlite3.connect(DATABASE)

months = ["jan", "feb", "mar", "apr", "may", "june", "july", "aug", "sep", "oct", "nov", "dec"]

def format_date(d):
    parsed = date.fromisoformat(d)
    month = months[parsed.month - 1]
    return f"{parsed.year} {month} {parsed.day}"

reviews = json.load(open("./backfill.json"))

for review in sorted(reviews, key=lambda review: review["date"]):
    print(review["title"])
    template_entry_id = db.execute(
        "insert into TemplateEntry(template_id) values ((select id from Template where name='Game reviews'))"
    ).lastrowid

    for field_name, field_value in review.items():
        if field_name == "date":
            field_value = format_date(field_value)
        value_json = json.dumps(field_value)
        db.execute("""
            INSERT INTO TemplateFieldValue(template_entry_id, template_field_id, value_json)
            VALUES(
                ?,
                (select id from TemplateField where field_name=? and template_id=(
                    (select id from Template where name='Game reviews')
                )),
                ?
            )
        """, (template_entry_id, field_name, value_json))

db.commit()
