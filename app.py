import json
import os
import base64
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file

from cryptohelper import hash_password, encrypt
from manager import manager

app = Flask(__name__)

CONFIG_PATH = 'conf.json'
BACKUP_PATH = 'backup.txt'
MEDIA_FOLDER = 'media'
EXPORTS_FOLDER = 'exports'
mgr = manager(CONFIG_PATH)

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)
if not os.path.exists(EXPORTS_FOLDER):
    os.makedirs(EXPORTS_FOLDER)


@app.route('/')
@app.route('/home')
@app.route('/workflow')
def index():
    return render_template('client.html')


@app.route('/update', methods=['GET'])
def update():
    password = request.args.get('password')

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured', 'need_setup': True}), 200

    if not password or not mgr.valid_passwd(password):
        return jsonify({'error': 'Password required'}), 400

    mgr.receive()
    mgr.save_config()

    chats_data = []
    for i, chat in enumerate(mgr.data.get('chats', [])):
        unread_count = 0
        has_unread = chat.get('new', False)
        if has_unread:
            for msg in chat.get('messages', []):
                if msg[1] == 0:
                    unread_count += 1

        chats_data.append({
            'chat_id': i,
            'name': chat.get('name', ''),
            'unread_count': unread_count,
            'has_unread': has_unread
        })

    return jsonify({
        'status': 'ok',
        'profile_name': mgr.data.get('name', 'USER'),
        'chats': chats_data,
        'emails': mgr.data.get('emails', [])
    }), 200


@app.route('/getchatmessages', methods=['GET'])
def get_chat_messages():
    password = request.args.get('password')
    chat_name = request.args.get('chatname')

    if not password or not chat_name:
        return jsonify({'error': 'Password and chatname required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    result = mgr.get_messages_from_chat(chat_name, password)

    if not result:
        return jsonify({'error': 'Chat not found or decryption failed'}), 502

    messages, name = result
    decrypted_messages = []
    for msg in messages:
        msg_data = {
            'content': msg[0],
            'is_outgoing': msg[1] == 1,
            'type': 'text'
        }

        if msg[0].startswith('[MEDIA:'):
            parts = msg[0].split(']', 1)
            if len(parts) == 2:
                filename = parts[0][7:]
                msg_data['type'] = 'media'
                msg_data['filename'] = filename
                msg_data['content'] = parts[1] if parts[1] else '[Файл]'

        decrypted_messages.append(msg_data)

    return jsonify({
        'status': 'ok',
        'chat_name': name,
        'messages': decrypted_messages
    }), 200


@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password') or request.json.get('password')

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured', 'need_setup': True}), 200

    if mgr.valid_passwd(password):
        return jsonify({'status': 'ok'}), 200

    return jsonify({'error': 'Invalid password'}), 401


@app.route('/register', methods=['POST'])
def register():
    password = request.form.get('password') or request.json.get('password')
    name = request.form.get('name') or request.json.get('name', 'USER')

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if mgr.data.get('hash') is not None:
        return jsonify({'error': 'Already configured'}), 503

    mgr.setup(password, name)
    mgr.save_config()
    return jsonify({'status': 'ok'}), 200


@app.route('/createchat', methods=['POST'])
def create_chat():
    password = request.form.get('password') or request.json.get('password')
    name = request.form.get('name') or request.json.get('name')

    if not password or not name:
        return jsonify({'error': 'Password and name required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    result = mgr.create_chat(password, name)

    if not result:
        return jsonify({'error': 'Chat creation failed'}), 502

    mgr.save_config()

    chat_id = None
    for i, chat in enumerate(mgr.data.get('chats', [])):
        if chat.get('name') == name:
            chat_id = i
            break

    return jsonify({
        'status': 'ok',
        'chat_id': chat_id,
        'chat_name': name
    }), 200


@app.route('/sendmessage', methods=['POST'])
def send_message():
    password = request.form.get('password') or request.json.get('password')
    chat_name = request.form.get('chatid') or request.json.get('chatid')
    message = request.form.get('message') or request.json.get('message')
    recipient_email = (
            request.form.get('recipient_email')
            or request.json.get('recipient_email')
    )
    sender_email = (
            request.form.get('sender_email')
            or request.json.get('sender_email')
    )

    if not password or not chat_name or not message:
        return jsonify(
            {'error': 'Password, chatid and message required'}
        ), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    chat = None
    for c in mgr.data.get('chats', []):
        if c.get('name') == chat_name:
            chat = c
            break

    if not chat:
        return jsonify({'error': 'Chat not found'}), 502

    if not recipient_email and chat.get('emails'):
        recipient_email = chat['emails'][0] if chat['emails'] else None

    if not sender_email and mgr.data.get('emails'):
        sender_email = (
            mgr.data['emails'][0]['email'] if mgr.data['emails'] else None
        )

    if not recipient_email or not sender_email:
        return jsonify(
            {'error': 'Recipient or sender email missing'}
        ), 502

    mgr.send_message(chat_name, message, recipient_email,
                     sender_email, password)
    mgr.save_config()

    return jsonify({'status': 'ok'}), 200


@app.route('/send_media', methods=['POST'])
def send_media():
    password = request.form.get('password') or request.json.get('password')
    chat_name = request.form.get('chatid') or request.json.get('chatid')
    recipient_email = (
            request.form.get('recipient_email')
            or request.json.get('recipient_email')
    )
    sender_email = (
            request.form.get('sender_email')
            or request.json.get('sender_email')
    )

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not password or not chat_name:
        return jsonify({'error': 'Password and chatid required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    chat = None
    for c in mgr.data.get('chats', []):
        if c.get('name') == chat_name:
            chat = c
            break

    if not chat:
        return jsonify({'error': 'Chat not found'}), 502

    if not recipient_email and chat.get('emails'):
        recipient_email = chat['emails'][0] if chat['emails'] else None

    if not sender_email and mgr.data.get('emails'):
        sender_email = (
            mgr.data['emails'][0]['email'] if mgr.data['emails'] else None
        )

    if not recipient_email or not sender_email:
        return jsonify(
            {'error': 'Recipient or sender email missing'}
        ), 502

    file_data = base64.b64encode(file.read()).decode('utf-8')
    media_message = f'[MEDIA:{file.filename}]{file_data}'

    mgr.send_message(chat_name, media_message, recipient_email,
                     sender_email, password)
    mgr.save_config()

    return jsonify({'status': 'ok', 'filename': file.filename}), 200


@app.route('/download_media', methods=['GET'])
def download_media():
    password = request.args.get('password')
    file_data_b64 = request.args.get('data')
    filename = request.args.get('filename', 'media_file')

    if not password or not file_data_b64:
        return jsonify({'error': 'Password and data required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    try:
        file_data = base64.b64decode(file_data_b64)
    except Exception:
        return jsonify({'error': 'Invalid base64 data'}), 400

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = f'{timestamp}_{filename}'
    filepath = os.path.join(MEDIA_FOLDER, safe_filename)

    with open(filepath, 'wb') as f:
        f.write(file_data)

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/save_media', methods=['POST'])
def save_media():
    password = request.form.get('password') or request.json.get('password')
    file_data_b64 = request.form.get('data') or request.json.get('data')
    filename = (
            request.form.get('filename')
            or request.json.get('filename', 'media_file')
    )

    if not password or not file_data_b64:
        return jsonify({'error': 'Password and data required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    try:
        file_data = base64.b64decode(file_data_b64)
    except Exception:
        return jsonify({'error': 'Invalid base64 data'}), 400

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = f'{timestamp}_{filename}'
    filepath = os.path.join(MEDIA_FOLDER, safe_filename)

    with open(filepath, 'wb') as f:
        f.write(file_data)

    return jsonify({
        'status': 'ok',
        'filename': safe_filename,
        'path': filepath
    }), 200


@app.route('/export_chat', methods=['POST'])
def export_chat():
    password = request.form.get('password') or request.json.get('password')
    chat_name = request.form.get('chat_name') or request.json.get('chat_name')

    if not password or not chat_name:
        return jsonify({'error': 'Password and chat_name required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    result = mgr.get_messages_from_chat(chat_name, password)

    if not result:
        return jsonify({'error': 'Chat not found or decryption failed'}), 502

    messages, name = result

    export_data = {
        'chat_name': name,
        'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_messages': len(messages),
        'messages': []
    }

    for i, msg in enumerate(messages, 1):
        msg_entry = {
            'id': i,
            'direction': 'outgoing' if msg[1] == 1 else 'incoming',
            'type': 'text',
            'content': msg[0]
        }

        if msg[0].startswith('[MEDIA:'):
            parts = msg[0].split(']', 1)
            if len(parts) == 2:
                msg_entry['type'] = 'media'
                msg_entry['filename'] = parts[0][7:]
                msg_entry['content'] = parts[1] if parts[1] else '[Файл]'

        export_data['messages'].append(msg_entry)

    date_str = datetime.now().strftime('%Y-%m-%d_H-%M-%S')
    safe_chat_name = "".join(
        c for c in chat_name if c.isalnum() or c in (' ', '_', '-')
    ).rstrip()
    filename = f'chat_{safe_chat_name}_{date_str}.json'
    filepath = os.path.join(EXPORTS_FOLDER, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return jsonify({
        'status': 'ok',
        'filename': filename,
        'path': filepath,
        'message': f'Чат "{chat_name}" экспортирован: {len(messages)} сообщений'
    }), 200


@app.route('/download_export', methods=['GET'])
def download_export():
    password = request.args.get('password')
    filename = request.args.get('filename')

    if not password or not filename:
        return jsonify({'error': 'Password and filename required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    filepath = os.path.join(EXPORTS_FOLDER, filename)
    if not os.path.abspath(filepath).startswith(
            os.path.abspath(EXPORTS_FOLDER)):
        return jsonify({'error': 'Invalid filename'}), 400

    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/list_exports', methods=['GET'])
def list_exports():
    password = request.args.get('password')

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    exports = []
    if os.path.exists(EXPORTS_FOLDER):
        for f in os.listdir(EXPORTS_FOLDER):
            if f.endswith('.json'):
                filepath = os.path.join(EXPORTS_FOLDER, f)
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        chat_name = data.get('chat_name', 'Unknown')
                        msg_count = data.get('total_messages', 0)
                except Exception:
                    chat_name = 'Unknown'
                    msg_count = 0

                exports.append({
                    'filename': f,
                    'chat_name': chat_name,
                    'messages': msg_count,
                    'size': size,
                    'date': datetime.fromtimestamp(mtime).strftime(
                        '%Y-%m-%d %H:%M'
                    )
                })

    exports.sort(key=lambda x: x['date'], reverse=True)

    return jsonify({
        'status': 'ok',
        'exports': exports
    }), 200


@app.route('/delete_export', methods=['POST'])
def delete_export():
    password = request.form.get('password') or request.json.get('password')
    filename = request.form.get('filename') or request.json.get('filename')

    if not password or not filename:
        return jsonify({'error': 'Password and filename required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    filepath = os.path.join(EXPORTS_FOLDER, filename)
    if not os.path.abspath(filepath).startswith(
            os.path.abspath(EXPORTS_FOLDER)):
        return jsonify({'error': 'Invalid filename'}), 400

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'status': 'ok'}), 200

    return jsonify({'error': 'File not found'}), 404


@app.route('/preview_import', methods=['POST'])
def preview_import():
    password = request.form.get('password') or request.json.get('password')

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    # Вариант 1: загружен файл
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        try:
            data = json.load(file)
        except Exception:
            return jsonify({'error': 'Invalid JSON file'}), 400

    # Вариант 2: файл из exports/
    else:
        filename = request.form.get('filename') or request.json.get('filename')
        if not filename:
            return jsonify({'error': 'File or filename required'}), 400

        filepath = os.path.join(EXPORTS_FOLDER, filename)
        if not os.path.abspath(filepath).startswith(
                os.path.abspath(EXPORTS_FOLDER)):
            return jsonify({'error': 'Invalid filename'}), 400

        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return jsonify({'error': 'Invalid JSON file'}), 400

    # Извлекаем информацию
    chat_name = data.get('chat_name', 'Unknown')
    total = data.get('total_messages', 0)
    messages = data.get('messages', [])

    # Показываем первые 3 сообщения для предпросмотра
    preview = []
    for msg in messages[:3]:
        preview.append({
            'direction': msg.get('direction', 'unknown'),
            'type': msg.get('type', 'text'),
            'content': (msg.get('content', '')[:100] + '...'
                        if len(msg.get('content', '')) > 100
                        else msg.get('content', '')),
            'filename': msg.get('filename', '')
        })

    # Проверяем, существует ли уже чат с таким именем
    existing = any(
        c.get('name') == chat_name
        for c in mgr.data.get('chats', [])
    )

    return jsonify({
        'status': 'ok',
        'chat_name': chat_name,
        'total_messages': total,
        'preview': preview,
        'exists': existing,
        'source': 'upload' if 'file' in request.files else 'exports'
    }), 200


@app.route('/import_chat', methods=['POST'])
def import_chat():
    password = request.form.get('password') or request.json.get('password')
    mode = request.form.get('mode', 'new')  # 'new' или 'append'

    if not password:
        return jsonify({'error': 'Password required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    # Загружаем данные из файла
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        try:
            import_data = json.load(file)
        except Exception:
            return jsonify({'error': 'Invalid JSON file'}), 400
        source = 'upload'
    else:
        filename = request.form.get('filename') or request.json.get('filename')
        if not filename:
            return jsonify({'error': 'File or filename required'}), 400

        filepath = os.path.join(EXPORTS_FOLDER, filename)
        if not os.path.abspath(filepath).startswith(
                os.path.abspath(EXPORTS_FOLDER)):
            return jsonify({'error': 'Invalid filename'}), 400

        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception:
            return jsonify({'error': 'Invalid JSON file'}), 400
        source = 'exports'

    chat_name = import_data.get('chat_name', 'Imported Chat')
    messages = import_data.get('messages', [])

    # Ищем существующий чат
    existing_chat = None
    existing_index = None
    for i, c in enumerate(mgr.data.get('chats', [])):
        if c.get('name') == chat_name:
            existing_chat = c
            existing_index = i
            break

    # Режим 'new': создаём новый чат (если имя занято — добавляем суффикс)
    if mode == 'new':
        original_name = chat_name
        counter = 1
        while any(c.get('name') == chat_name
                  for c in mgr.data.get('chats', [])):
            chat_name = f'{original_name} ({counter})'
            counter += 1

        # Создаём чат через менеджер
        result = mgr.create_chat(password, chat_name)
        if not result:
            return jsonify({'error': 'Chat creation failed'}), 502

        # Находим только что созданный чат
        for c in mgr.data.get('chats', []):
            if c.get('name') == chat_name:
                existing_chat = c
                break

    # Режим 'append': добавляем в существующий
    elif mode == 'append' and existing_chat is None:
        # Если чата нет — создаём новый
        result = mgr.create_chat(password, chat_name)
        if not result:
            return jsonify({'error': 'Chat creation failed'}), 502
        for c in mgr.data.get('chats', []):
            if c.get('name') == chat_name:
                existing_chat = c
                break

    if existing_chat is None:
        return jsonify({'error': 'Could not find or create chat'}), 502

    # Расшифровываем ключ чата для шифрования импортируемых сообщений
    try:
        from cryptohelper import encrypt_message, decrypt
        enc_key = decrypt(password, existing_chat['enckey'].encode()).decode()
    except Exception:
        return jsonify({'error': 'Decryption failed'}), 502

    imported_count = 0
    for msg in messages:
        content = msg.get('content', '')
        msg_type = msg.get('type', 'text')
        direction = msg.get('direction', 'incoming')
        filename = msg.get('filename', '')

        # Формируем тело сообщения
        if msg_type == 'media' and filename:
            # Медиасообщение
            if not content.startswith('[MEDIA:'):
                content = f'[MEDIA:{filename}]{content}'

        # Шифруем и добавляем
        try:
            encrypted = encrypt_message(
                enc_key,
                existing_chat['routekey'],
                existing_chat['route'],
                content
            )
            is_outgoing = 1 if direction == 'outgoing' else 0
            existing_chat['messages'].append((encrypted, is_outgoing))
            imported_count += 1
        except Exception as e:
            print(f"Error importing message: {e}")

    mgr.save_config()

    return jsonify({
        'status': 'ok',
        'chat_name': chat_name,
        'imported': imported_count,
        'total': len(messages),
        'mode': mode,
        'source': source
    }), 200


@app.route('/add_email', methods=['POST'])
def add_email():
    password = request.form.get('password') or request.json.get('password')
    email = request.form.get('email')
    apikey = request.form.get('apikey')

    if not password or not email or not apikey:
        return jsonify({'error': 'Password, email and apikey required'}), 400

    if mgr.data.get('hash') is None:
        return jsonify({'error': 'Not configured'}), 503

    if not mgr.valid_passwd(password):
        return jsonify({'error': 'Invalid password'}), 401

    if mgr.setup_email(email, apikey):
        mgr.save_config()
        return jsonify({'status': 'ok'}), 200

    return jsonify({'error': 'Email already exists'}), 409


def main():
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()