from flask import Flask

from models.user import db as user_db
from models.message import db as message_db
from flask import render_template, redirect, session
from models.user import User
from models.message import Message
from routes.auth import register_routes as register_auth
from routes.users import register_routes as register_users
from routes.messages import register_routes as register_messages

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messenger.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

user_db.init_app(app)
# message_db.init_app(app)

register_auth(app)
register_users(app)
register_messages(app)


@app.route('/')
def index_page():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])
    return render_template('index.html', user=user)


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/users')
def users_page():
    if 'user_id' not in session:
        return redirect('/login')

    users = User.query.filter(User.id != session['user_id']).all()
    return render_template('users.html', users=users)


@app.route('/chat/<user_uuid>')
def chat_page(user_uuid):
    if 'user_id' not in session:
        return redirect('/login')

    current_user = User.query.get(session['user_id'])
    other_user = User.query.filter_by(uuid=user_uuid).first()

    if not other_user:
        return redirect('/users')

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    return render_template('chat.html', user=current_user, other_user=other_user, messages=messages)


@app.route('/logout')
def logout_page():
    session.clear()
    return redirect('/login')


def main():
    with app.app_context():
        user_db.create_all()

    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
