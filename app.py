from flask import Flask, render_template, redirect, session, request, jsonify
import data.db_session as db_session
from data.user import User
from data.message import Message
from datetime import datetime
import uuid
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'mowl_secret_key'


def init_db():
    os.makedirs('db', exist_ok=True)
    db_session.global_init('mowl.db')


@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('landing.html')
    sess = db_session.create_session()
    user = sess.query(User).get(session['user_id'])
    users = sess.query(User).filter(User.id != session['user_id']).all()
    sess.close()
    return render_template('index.html', user=user, users=users)


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/chat/<user_uuid>')
def chat_page(user_uuid):
    if 'user_id' not in session:
        return redirect('/login')
    sess = db_session.create_session()
    current_user = sess.query(User).get(session['user_id'])
    other_user = sess.query(User).filter(User.uuid == user_uuid).first()
    if not other_user:
        sess.close()
        return redirect('/')
    all_users = sess.query(User).filter(User.id != session['user_id']).all()
    messages = sess.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    sess.close()
    return render_template('chat.html',
                           user=current_user,
                           other_user=other_user,
                           messages=messages,
                           all_users=all_users)


@app.route('/api/messages/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    current_user_id = session['user_id']
    recipient_uuid = request.form.get('recipient_id') or request.json.get('recipient_id')
    content = request.form.get('content') or request.json.get('content')
    if not recipient_uuid or not content:
        return jsonify({'error': 'Не указан получатель или сообщение пустое'}), 400
    sess = db_session.create_session()
    recipient = sess.query(User).filter(User.uuid == recipient_uuid).first()
    if not recipient:
        sess.close()
        return jsonify({'error': 'Получатель не найден'}), 404
    message = Message(
        uuid=str(uuid.uuid4()),
        sender_id=current_user_id,
        recipient_id=recipient.id,
        content=content.strip(),
        delivered_at=datetime.now()
    )
    sess.add(message)
    sess.commit()
    sess.close()
    return jsonify({'success': True, 'message': 'Сообщение отправлено'})


@app.route('/api/login', methods=['POST'])
def api_login():
    phone = request.form.get('phone') or request.json.get('phone')
    password = request.form.get('password') or request.json.get('password')
    if not phone or not password:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Заполните все поля'}), 400
        return render_template('login.html', error='Заполните все поля')
    sess = db_session.create_session()
    user = sess.query(User).filter(User.phone == phone, User.password == password).first()
    if not user:
        sess.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Неверный телефон или пароль'}), 401
        return render_template('login.html', error='Неверный телефон или пароль')
    session['user_id'] = user.id
    session['user_uuid'] = user.uuid
    user.last_seen = datetime.now()
    sess.commit()
    sess.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'redirect': '/'})
    return redirect('/')


@app.route('/api/register', methods=['POST'])
def api_register():
    phone = request.form.get('phone') or request.json.get('phone')
    full_name = request.form.get('full_name') or request.json.get('full_name')
    password = request.form.get('password') or request.json.get('password')
    if not phone or not full_name or not password:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Заполните все поля'}), 400
        return render_template('register.html', error='Заполните все поля')
    sess = db_session.create_session()
    if sess.query(User).filter(User.phone == phone).first():
        sess.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Пользователь уже существует'}), 409
        return render_template('register.html', error='Пользователь уже существует')
    user = User(
        uuid=str(uuid.uuid4()),
        phone=phone,
        full_name=full_name,
        password=password
    )
    sess.add(user)
    sess.commit()
    session['user_id'] = user.id
    session['user_uuid'] = user.uuid
    sess.close()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'redirect': '/'})
    return redirect('/')


def main():
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
