from flask import Flask
from models.user import db as user_db
from models.message import db as message_db

from routes.auth import register_routes as register_auth
from routes.users import register_routes as register_users
from routes.messages import register_routes as register_messages

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messenger.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

user_db.init_app(app)
message_db.init_app(app)

register_auth(app)
register_users(app)
register_messages(app)


def main():
    with app.app_context():
        user_db.create_all()

    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()