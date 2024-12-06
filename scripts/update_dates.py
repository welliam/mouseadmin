from datetime import date
import os
import json
import sqlite3

db = sqlite3.connect(os.getenv("MOUSEADMIN_DB"))

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
    "dec"
]

def parse_short_date(s):
    try:
        [year, month_string, day] = s.split(' ')
        return date(int(year), month_list.index(month_string) + 1, int(day))
    except ValueError:
        return None

for id, value_json in db.execute("select id, value_json from TemplateFieldValue where template_field_name = 'date'").fetchall():
    parsed = parse_short_date(json.loads(value_json))
    if parsed:
        updated_date = json.dumps(str(parsed))
        print("update TemplateFieldValue set value_json=? where id=?", [updated_date, id])
        db.execute("update TemplateFieldValue set value_json=? where id=?", [updated_date, id])

db.commit()
