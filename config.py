class Config:
    SECRET_KEY = 'yandexlyceum_secret_key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///messenger.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

config = Config()
