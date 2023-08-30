# run:
# sudo cp service.sh /usr/bin/mouseadmin_service.sh
# sudo chmod +x /usr/bin/mouseadmin_service.sh

cd /home/wellpi/prog/mouseadmin
. env/bin/activate
flask run --host 0.0.0.0
