from flask import request, jsonify, session
from models.user import User, db
from middleware.auth_middleware import login_required


def register_routes(app):
    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.json
        phone = data.get('phone')
        full_name = data.get('full_name')
        password = data.get('password')

        if not phone or not full_name or not password:
            return jsonify({'error': 'error'}), 400

        if User.query.filter_by(phone=phone).first():
            return jsonify({'error': 'error'}), 409

        user = User(
            phone=phone,
            full_name=full_name,
            password=password
        )

        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        session['user_uuid'] = user.uuid

        return jsonify({
            'success': True,
            'message': 'Регистрация успешна',
            'user': {
                'id': user.uuid,
                'phone': user.phone,
                'full_name': user.full_name
            }
        }), 201

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.json
        phone = data.get('phone')
        password = data.get('password')

        if not phone or not password:
            return jsonify({'error': 'error'}), 400

        user = User.query.filter_by(phone=phone, password=password).first()

        if not user:
            return jsonify({'error': 'error'}), 401

        session['user_id'] = user.id
        session['user_uuid'] = user.uuid

        from datetime import datetime

        user.last_seen = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Вход выполнен',
            'user': {
                'id': user.uuid,
                'phone': user.phone,
                'full_name': user.full_name
            }
        })

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout():
        session.clear()
        return jsonify({'success': True, 'message': 'Выход выполнен'})

    @app.route('/api/check-auth', methods=['GET'])
    def check_auth():
        if 'user_id' in session:
            user = User.query.get(session['user_id'])

            if user:
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'id': user.uuid,
                        'phone': user.phone,
                        'full_name': user.full_name
                    }
                })

        return jsonify({'authenticated': False})
