# todo #

## Setup project ##

```
cd  
mkdir Python  
git clone https://github.com/jean-petitclerc/todo.git  
python3 -m venv --system-site-packages venv
. venv/bin/activate
pip install Flask
pip install flask-wtf
pip install email-validator
pip install flask-script
pip install flask-sqlalchemy
pip install flask-bootstrap
sudo apt install postgresql-all
pip install psycopg2
```

## Create database ##
```
psql
create database <db>;
create role <user> login nosuperuser inherit nocreatedb noreplication;
alter user <user> password 'xxxxxx';
grant all on database <db> to <user>;
```

## Create config.py ##
```
class Config(object):
    pass

class ProdConfig(Config):
    pass


class DevConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://<user>:<password>@<server>:5432/<db>"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = '<secret_key>'
```

## Create tables ##
```
python
from main import db
db.create_all()
exit(0)
```

## Run application ##
```
python main.py runserver -h 0.0.0.0
```