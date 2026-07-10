set -e
python manage.py migrate
python manage.py createcachetable cache_table
python manage.py qcluster &
exec gunicorn --bind=0.0.0.0:8080 --timeout 600 vvp_app_server.wsgi --access-logfile '-' --error-logfile '-'
