import os


class Config:
    SECRET_KEY = "smartbooks_secret_key"

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "smartbooks.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False