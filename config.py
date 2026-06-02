class Config:
    SECRET_KEY = "smartbooks_secret_key"

    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://root@localhost/online_bookstore"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False