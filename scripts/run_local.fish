. env/bin/activate.fish
find src -type f | FLASK_APP=src/mouseadmin/app.py entr -r flask run
