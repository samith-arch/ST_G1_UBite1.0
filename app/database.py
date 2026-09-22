import os
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "database", "ubite.db")

db = SQLAlchemy()


def get_database_uri():
    return f"sqlite:///{DB_PATH}"
