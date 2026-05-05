from flask import session, jsonify


def login_required(f):
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'error'}), 401

        return f(*args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


def get_current_user_id():
    return session.get('user_id')
