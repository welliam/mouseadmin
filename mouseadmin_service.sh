# run:
# sudo cp mouseadmin_service.sh /usr/bin/mouseadmin_service.sh
# sudo chmod +x /usr/bin/mouseadmin_service.sh

cd /home/well/prog/mouseadmin
. env/bin/activate
MOUSEADMIN_DB=mouseadmin.db NEOCITIES_CLIENT=neocities FLASK_APP=src/mouseadmin/app.py flask run --host 0.0.0.0
