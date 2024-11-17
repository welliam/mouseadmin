#!/home/well/.nix-profile/bin/fish

if test testdb.db
    rm testdb.db
end
sqlite3 testdb.db < schema.sql &&

. env/bin/activate.fish &&
MOUSEADMIN_DB=testdb.db FLASK_APP=src/mouseadmin/app.py flask run --debug --host 0.0.0.0 --port 5555 &
sleep 1 && ./puppeteer-test.js
kill $last_pid
rm testdb.db
