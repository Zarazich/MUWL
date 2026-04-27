from flask import request, jsonify, session
from models.user import User
from middleware.auth_middleware import login_required


def register_routes(app):
    @app.route('/api/users/me', methods=['GET'])
    @login_required
    def get_current_user():
        user = User.query.get(session['user_id'])

        if not user:
            session.clear()
            return jsonify({'error': 'error'}), 401

        return jsonify({
            'id': user.uuid,
            'phone': user.phone,
            'full_name': user.full_name,
            'created_at': user.created_at.isoformat(),
            'last_seen': user.last_seen.isoformat()
        })

    @app.route('/api/users/<user_uuid>', methods=['GET'])
    @login_required
    def get_user_by_uuid(user_uuid):
        user = User.query.filter_by(uuid=user_uuid).first()

        if not user:
            return jsonify({'error': 'error'}), 404

        return jsonify({
            'id': user.uuid,
            'phone': user.phone,
            'full_name': user.full_name
        })

    @app.route('/api/users/search', methods=['GET'])
    @login_required
    def search_users():
        query = request.args.get('q', '').strip()
        current_user_id = session['user_id']

        if not query or len(query) < 2:
            return jsonify({'users': []})

        users = User.query.filter(
            (User.full_name.ilike(f'%{query}%')) |
            (User.phone.ilike(f'%{query}%'))
        ).limit(20).all()

        result = []
        for u in users:
            if u.id != current_user_id:
                result.append({
                    'id': u.uuid,
                    'phone': u.phone,
                    'full_name': u.full_name
                })

        return jsonify({'users': result})

    @app.route('/api/users/all', methods=['GET'])
    @login_required
    def get_all_users():
        current_user_id = session['user_id']
        users = User.query.filter(User.id != current_user_id).all()

        return jsonify({
            'users': [{
                'id': u.uuid,
                'phone': u.phone,
                'full_name': u.full_name
            } for u in users]
        })
