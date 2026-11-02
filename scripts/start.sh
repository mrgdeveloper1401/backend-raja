#!/bin/bash

python manage.py collectstatic --noinput
python manage.py makemigrations
python manage.py migrate
python manage.py sync_stations
python manage.py runbolt --processes 2