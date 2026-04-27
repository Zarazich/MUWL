from flask import request, jsonify, session
from datetime import datetime
from models.message import Message, db
from models.user import User
from middleware.auth_middleware import login_required


def register_routes(app):
    @app.route('/api/messages/send', methods=['POST'])
    @login_required
    def send_message():
        data = request.json
        current_user_id = session['user_id']

        recipient_uuid = data.get('recipient_id')
        content = data.get('content')

        if not recipient_uuid:
            return jsonify({'error': 'Не указан получатель'}), 400

        if not content or not content.strip():
            return jsonify({'error': 'Сообщение не может быть пустым'}), 400

        recipient = User.query.filter_by(uuid=recipient_uuid).first()
        if not recipient:
            return jsonify({'error': 'Получатель не найден'}), 404

        message = Message(
            sender_id=current_user_id,
            recipient_id=recipient.id,
            content=content.strip(),
            delivered_at=datetime.utcnow()
        )

        db.session.add(message)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Сообщение отправлено',
            'data': {
                'id': message.uuid,
                'to': recipient.uuid,
                'to_name': recipient.full_name,
                'content': message.content,
                'created_at': message.created_at.isoformat()
            }
        }), 201

    @app.route('/api/messages/inbox', methods=['GET'])
    @login_required
    def get_inbox():
        current_user_id = session['user_id']

        messages = Message.query.filter_by(
            recipient_id=current_user_id
        ).order_by(Message.created_at.desc()).limit(100).all()

        return jsonify({
            'messages': [{
                'id': m.uuid,
                'from_user': m.sender.uuid,
                'from_name': m.sender.full_name,
                'content': m.content,
                'is_read': m.is_read,
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })

    @app.route('/api/messages/outbox', methods=['GET'])
    @login_required
    def get_outbox():
        current_user_id = session['user_id']

        messages = Message.query.filter_by(
            sender_id=current_user_id
        ).order_by(Message.created_at.desc()).limit(100).all()

        return jsonify({
            'messages': [{
                'id': m.uuid,
                'to_user': m.recipient.uuid,
                'to_name': m.recipient.full_name,
                'content': m.content,
                'is_read': m.is_read,
                'created_at': m.created_at.isoformat(),
                'read_at': m.read_at.isoformat() if m.read_at else None
            } for m in messages]
        })

    @app.route('/api/messages/<message_uuid>/read', methods=['PUT'])
    @login_required
    def mark_as_read(message_uuid):
        current_user_id = session['user_id']

        message = Message.query.filter_by(uuid=message_uuid).first()

        if not message:
            return jsonify({'error': 'error'}), 404

        if message.recipient_id != current_user_id:
            return jsonify({'error': 'error'}), 403

        if not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()

        return jsonify({'success': True, 'message': 'прочитано'})

    @app.route('/api/messages/<message_uuid>', methods=['DELETE'])
    @login_required
    def delete_message(message_uuid):
        current_user_id = session['user_id']
        message = Message.query.filter_by(uuid=message_uuid).first()

        if not message:
            return jsonify({'error': 'error'}), 404

        if message.sender_id != current_user_id:
            return jsonify({'error': 'error'}), 403

        db.session.delete(message)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Сообщение удалено'})

    @app.route('/api/messages/unread/count', methods=['GET'])
    @login_required
    def get_unread_count():
        current_user_id = session['user_id']

        count = Message.query.filter_by(
            recipient_id=current_user_id,
            is_read=False
        ).count()

        return jsonify({'unread_count': count})

    @app.route('/api/messages/chat/<user_uuid>', methods=['GET'])
    @login_required
    def get_chat_history(user_uuid):
        current_user_id = session['user_id']
        other_user = User.query.filter_by(uuid=user_uuid).first()

        if not other_user:
            return jsonify({'error': 'error'}), 404

        messages = Message.query.filter(
            ((Message.sender_id == current_user_id) & (Message.recipient_id == other_user.id)) |
            ((Message.sender_id == other_user.id) & (Message.recipient_id == current_user_id))
        ).order_by(Message.created_at.asc()).all()

        return jsonify({
            'with_user': {
                'id': other_user.uuid,
                'name': other_user.full_name,
                'phone': other_user.phone
            },
            'messages': [{
                'id': m.uuid,
                'from': m.sender.uuid,
                'from_name': m.sender.full_name,
                'to': m.recipient.uuid,
                'content': m.content,
                'is_read': m.is_read,
                'created_at': m.created_at.isoformat()
            } for m in messages]
        })
