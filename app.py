import json
import os
import base64
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file

from manager import manager

app = Flask(__name__)

CONFIG_PATH = "conf.json"
MEDIA_FOLDER = "media"
EXPORTS_FOLDER = "exports"
AVATARS_FOLDER = "avatars"

mgr = manager(CONFIG_PATH)

for folder in [MEDIA_FOLDER, EXPORTS_FOLDER, AVATARS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)


def get_password():
    pwd = request.form.get("password") or request.json.get("password") or request.args.get("password")
    return pwd


def check_auth():
    password = get_password()

    if mgr.data.get("hash") is None:
        return False, None, "Not configured", 200

    if not password:
        return False, None, "Password required", 400

    if not mgr.valid_passwd(password):
        return False, None, "Invalid password", 401

    return True, password, None, 200


@app.route("/")
@app.route("/home")
@app.route("/workflow")
def index():
    return render_template("client.html")


@app.route("/check_setup", methods=["GET"])
def check_setup():
    if mgr.data.get("hash") is None:
        return jsonify({"need_setup": True, "configured": False}), 200
    return jsonify({"need_setup": False, "configured": True}), 200


@app.route("/update", methods=["GET"])
def update():
    valid, password, error, code = check_auth()

    if mgr.data.get("hash") is None:
        return jsonify({"need_setup": True, "error": "Not configured"}), 200

    if not valid:
        return jsonify({"error": error}), code

    mgr.receive()
    mgr.save_config()

    chats_data = []
    total_unread = 0

    for i, chat in enumerate(mgr.data.get("chats", [])):
        unread_count = 0
        if chat.get("unreaden", False):
            for msg in chat.get("messages", []):
                if msg[1] == 0:
                    unread_count += 1
            total_unread += unread_count

        last_message = ""
        if chat.get("messages") and len(chat["messages"]) > 0:
            try:
                enc_key = mgr.decrypt_chat_key(chat.get("name"), password)
                if enc_key:
                    from cryptohelper import decrypt_message
                    last_enc = chat["messages"][-1][0]
                    last_msg = decrypt_message(chat["routekey"], enc_key, last_enc)
                    if last_msg.startswith("[MEDIA:"):
                        last_message = "📎 Файл"
                    else:
                        last_message = last_msg[:40] + ("..." if len(last_msg) > 40 else "")
            except:
                last_message = "🔒 Зашифровано"
        else:
            last_message = "Нет сообщений"

        safe_name = "".join(c for c in chat.get("name", "") if c.isalnum() or c in " _-")
        avatar_path = os.path.join(AVATARS_FOLDER, f"chat_{safe_name}.txt")
        chat_avatar = None
        if os.path.exists(avatar_path):
            with open(avatar_path, "r") as f:
                chat_avatar = f.read()

        chats_data.append({
            "chat_id": i,
            "name": chat.get("name", ""),
            "unread_count": unread_count,
            "has_unread": chat.get("unreaden", False),
            "last_message": last_message,
            "emails": chat.get("emails", []),
            "avatar": chat_avatar
        })

    return jsonify({
        "status": "ok",
        "profile_name": mgr.data.get("name", "USER"),
        "chats": chats_data,
        "emails": mgr.data.get("emails", []),
        "total_unread": total_unread
    }), 200


@app.route("/getchatmessages", methods=["GET"])
def get_chat_messages():
    valid, password, error, code = check_auth()
    chat_name = request.args.get("chatname")

    if not valid:
        return jsonify({"error": error}), code

    if not chat_name:
        return jsonify({"error": "Chat name required"}), 400

    result = mgr.get_messages_from_chat(chat_name, password)

    if result is None:
        return jsonify({"error": "Chat not found or decryption failed"}), 502

    messages, name = result
    decrypted_messages = []

    for msg in messages:
        msg_data = {
            "content": msg[0],
            "is_outgoing": msg[1] == 1,
            "type": "text"
        }

        if msg[0].startswith("[MEDIA:"):
            parts = msg[0].split("]", 1)
            if len(parts) == 2:
                msg_data["type"] = "media"
                msg_data["filename"] = parts[0][7:]
                msg_data["content"] = parts[1] if parts[1] else "[Файл]"

        decrypted_messages.append(msg_data)

    return jsonify({
        "status": "ok",
        "chat_name": name,
        "messages": decrypted_messages
    }), 200


@app.route("/login", methods=["POST"])
def login():
    password = get_password()

    if mgr.data.get("hash") is None:
        return jsonify({"error": "Not configured", "need_setup": True}), 200

    if not password:
        return jsonify({"error": "Password required"}), 400

    if mgr.valid_passwd(password):
        return jsonify({"status": "ok", "profile_name": mgr.data.get("name")}), 200

    return jsonify({"error": "Invalid password"}), 401


@app.route("/register", methods=["POST"])
def register():
    password = request.form.get("password")
    name = request.form.get("name", "USER")

    if not password:
        return jsonify({"error": "Password required", "status": "error"}), 400

    if mgr.data.get("hash") is not None:
        return jsonify({"error": "Already configured", "status": "error"}), 503

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters", "status": "error"}), 400

    mgr.setup(password, name)
    mgr.save_config()

    return jsonify({"status": "ok", "profile_name": name}), 200


@app.route("/rename_chat", methods=["POST"])
def rename_chat():
    valid, password, error, code = check_auth()
    old_name = request.form.get("old_name")
    new_name = request.form.get("new_name")

    if not valid:
        return jsonify({"error": error}), code

    if not old_name or not new_name:
        return jsonify({"error": "Old and new name required"}), 400

    for chat in mgr.data.get("chats", []):
        if chat.get("name") == new_name:
            return jsonify({"error": "Chat name already exists"}), 409

    for chat in mgr.data.get("chats", []):
        if chat.get("name") == old_name:
            chat["name"] = new_name

            old_avatar = os.path.join(AVATARS_FOLDER, f"chat_{old_name}.txt")
            new_avatar = os.path.join(AVATARS_FOLDER, f"chat_{new_name}.txt")
            if os.path.exists(old_avatar):
                os.rename(old_avatar, new_avatar)

            mgr.save_config()
            return jsonify({"status": "ok", "new_name": new_name}), 200

    return jsonify({"error": "Chat not found"}), 404


@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    valid, password, error, code = check_auth()
    chat_name = request.form.get("chat_name")

    if not valid:
        return jsonify({"error": error}), code

    if not chat_name:
        return jsonify({"error": "Chat name required"}), 400

    for i, chat in enumerate(mgr.data.get("chats", [])):
        if chat.get("name") == chat_name:
            mgr.data["chats"].pop(i)

            safe_name = "".join(c for c in chat_name if c.isalnum() or c in " _-")
            avatar_path = os.path.join(AVATARS_FOLDER, f"chat_{safe_name}.txt")
            if os.path.exists(avatar_path):
                os.remove(avatar_path)

            mgr.save_config()
            return jsonify({"status": "ok"}), 200

    return jsonify({"error": "Chat not found"}), 404


@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    valid, password, error, code = check_auth()
    target = request.form.get("target")
    avatar_data = request.form.get("avatar")

    if not valid:
        return jsonify({"error": error}), code

    if not target:
        return jsonify({"error": "Target required"}), 400

    if target == "profile":
        return jsonify({"error": "Profile avatars not supported"}), 400

    chat_exists = False
    for chat in mgr.data.get("chats", []):
        if chat.get("name") == target:
            chat_exists = True
            break

    if not chat_exists:
        return jsonify({"error": "Chat not found"}), 404

    safe_name = "".join(c for c in target if c.isalnum() or c in " _-")
    avatar_path = os.path.join(AVATARS_FOLDER, f"chat_{safe_name}.txt")

    if avatar_data:
        with open(avatar_path, "w") as f:
            f.write(avatar_data)
    elif os.path.exists(avatar_path):
        os.remove(avatar_path)

    return jsonify({"status": "ok", "target": target}), 200


@app.route("/createchat", methods=["POST"])
def create_chat():
    valid, password, error, code = check_auth()
    name = request.form.get("name")
    recipient_email = request.form.get("recipient_email", "")

    if not valid:
        return jsonify({"error": error}), code

    if not name:
        return jsonify({"error": "Chat name required"}), 400

    result = mgr.create_chat(password, name)

    if result is None:
        return jsonify({"error": "Chat creation failed - name may already exist"}), 502

    if isinstance(result, tuple) and len(result) == 4:
        if recipient_email:
            for chat in mgr.data.get("chats", []):
                if chat.get("name") == name:
                    if recipient_email not in chat.get("emails", []):
                        chat["emails"].append(recipient_email)
                    break
            mgr.save_config()

        return jsonify({"status": "ok", "chat_name": name, "chat_id": name}), 200

    return jsonify({"error": "Chat creation failed"}), 502


@app.route("/sendmessage", methods=["POST"])
def send_message():
    valid, password, error, code = check_auth()
    chat_name = request.form.get("chatid")
    message = request.form.get("message")
    recipient_email = request.form.get("recipient_email")
    sender_email = request.form.get("sender_email")

    if not valid:
        return jsonify({"error": error}), code

    if not chat_name:
        return jsonify({"error": "Chat id required"}), 400

    if not message:
        return jsonify({"error": "Message required"}), 400

    chat = None
    for c in mgr.data.get("chats", []):
        if c.get("name") == chat_name:
            chat = c
            break

    if not chat:
        return jsonify({"error": "Chat not found"}), 502

    final_recipient = recipient_email
    if not final_recipient and chat.get("emails"):
        final_recipient = chat["emails"][0]

    final_sender = sender_email
    if not final_sender and mgr.data.get("emails"):
        final_sender = mgr.data["emails"][0]["email"]

    if not final_recipient:
        return jsonify({"error": "Recipient email missing"}), 502

    if not final_sender:
        return jsonify({"error": "Sender email missing - add email account first"}), 502

    mgr.send_message(chat_name, message, final_recipient, final_sender, password)
    mgr.save_config()

    return jsonify({"status": "ok"}), 200


@app.route("/send_media", methods=["POST"])
def send_media():
    valid, password, error, code = check_auth()
    chat_name = request.form.get("chatid")
    recipient_email = request.form.get("recipient_email")
    sender_email = request.form.get("sender_email")
    caption = request.form.get("message", "")

    if not valid:
        return jsonify({"error": error}), code

    if not chat_name:
        return jsonify({"error": "Chat id required"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        return jsonify({"error": "File too large (max 5MB)"}), 400

    chat = None
    for c in mgr.data.get("chats", []):
        if c.get("name") == chat_name:
            chat = c
            break

    if not chat:
        return jsonify({"error": "Chat not found"}), 502

    final_recipient = recipient_email
    if not final_recipient and chat.get("emails"):
        final_recipient = chat["emails"][0]

    final_sender = sender_email
    if not final_sender and mgr.data.get("emails"):
        final_sender = mgr.data["emails"][0]["email"]

    if not final_recipient:
        return jsonify({"error": "Recipient email missing"}), 502

    if not final_sender:
        return jsonify({"error": "Sender email missing - add email account first"}), 502

    file_data = base64.b64encode(file.read()).decode("utf-8")

    if caption:
        media_message = f"[MEDIA:{file.filename}]{caption}\n[FILE_DATA]{file_data}"
    else:
        media_message = f"[MEDIA:{file.filename}]{file_data}"

    mgr.send_message(chat_name, media_message, final_recipient, final_sender, password)
    mgr.save_config()

    return jsonify({"status": "ok", "filename": file.filename}), 200


@app.route("/download_media", methods=["GET"])
def download_media():
    valid, password, error, code = check_auth()
    file_data_b64 = request.args.get("data")
    filename = request.args.get("filename", "media_file")

    if not valid:
        return jsonify({"error": error}), code

    if not file_data_b64:
        return jsonify({"error": "No data provided"}), 400

    if "[FILE_DATA]" in file_data_b64:
        file_data_b64 = file_data_b64.split("[FILE_DATA]")[-1]

    try:
        file_data = base64.b64decode(file_data_b64)
    except Exception:
        return jsonify({"error": "Invalid base64 data"}), 400

    return send_file(
        BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype='application/octet-stream'
    )


@app.route("/add_email", methods=["POST"])
def add_email():
    valid, password, error, code = check_auth()
    email = request.form.get("email")
    apikey = request.form.get("apikey")

    if not valid:
        return jsonify({"error": error}), code

    if not email or not apikey:
        return jsonify({"error": "Email and apikey required"}), 400

    if mgr.setup_email(email, apikey):
        mgr.save_config()
        return jsonify({"status": "ok"}), 200

    return jsonify({"error": "Email already exists"}), 409


@app.route("/export_chat", methods=["POST"])
def export_chat():
    valid, password, error, code = check_auth()
    chat_name = request.form.get("chat_name")

    if not valid:
        return jsonify({"error": error}), code

    if not chat_name:
        return jsonify({"error": "Chat name required"}), 400

    result = mgr.get_messages_from_chat(chat_name, password)

    if result is None:
        return jsonify({"error": "Chat not found or decryption failed"}), 502

    messages, name = result

    export_data = {
        "chat_name": name,
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_messages": len(messages),
        "messages": []
    }

    for i, msg in enumerate(messages, 1):
        msg_entry = {
            "id": i,
            "direction": "outgoing" if msg[1] == 1 else "incoming",
            "type": "text",
            "content": msg[0]
        }

        if msg[0].startswith("[MEDIA:"):
            parts = msg[0].split("]", 1)
            if len(parts) == 2:
                msg_entry["type"] = "media"
                msg_entry["filename"] = parts[0][7:]
                content = parts[1]
                if "[FILE_DATA]" in content:
                    content = content.split("[FILE_DATA]")[0]
                msg_entry["content"] = content.strip()

        export_data["messages"].append(msg_entry)

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_chat_name = "".join(c for c in chat_name if c.isalnum() or c in (" ", "_", "-")).rstrip()
    filename = f"chat_{safe_chat_name}_{date_str}.json"
    filepath = os.path.join(EXPORTS_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return jsonify({
        "status": "ok",
        "filename": filename,
        "message": f'Чат "{chat_name}" экспортирован: {len(messages)} сообщений'
    }), 200


@app.route("/list_exports", methods=["GET"])
def list_exports():
    valid, password, error, code = check_auth()

    if not valid:
        return jsonify({"error": error}), code

    exports = []
    if os.path.exists(EXPORTS_FOLDER):
        for f in os.listdir(EXPORTS_FOLDER):
            if f.endswith(".json"):
                filepath = os.path.join(EXPORTS_FOLDER, f)
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        chat_name = data.get("chat_name", "Unknown")
                        msg_count = data.get("total_messages", 0)
                except Exception:
                    chat_name = "Unknown"
                    msg_count = 0

                exports.append({
                    "filename": f,
                    "chat_name": chat_name,
                    "messages": msg_count,
                    "size": size,
                    "date": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                })

    exports.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({"status": "ok", "exports": exports}), 200


@app.route("/download_export", methods=["GET"])
def download_export():
    valid, password, error, code = check_auth()
    filename = request.args.get("filename")

    if not valid:
        return jsonify({"error": error}), code

    if not filename:
        return jsonify({"error": "Filename required"}), 400

    filepath = os.path.join(EXPORTS_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route("/delete_export", methods=["POST"])
def delete_export():
    valid, password, error, code = check_auth()
    filename = request.form.get("filename")

    if not valid:
        return jsonify({"error": error}), code

    if not filename:
        return jsonify({"error": "Filename required"}), 400

    filepath = os.path.join(EXPORTS_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"status": "ok"}), 200

    return jsonify({"error": "File not found"}), 404


@app.route("/import_chat", methods=["POST"])
def import_chat():
    valid, password, error, code = check_auth()
    mode = request.form.get("mode", "append")

    if not valid:
        return jsonify({"error": error}), code

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        import_data = json.load(file)
    except Exception:
        return jsonify({"error": "Invalid JSON file"}), 400

    chat_name = import_data.get("chat_name", "Imported Chat")
    messages = import_data.get("messages", [])

    existing_chat = None
    for c in mgr.data.get("chats", []):
        if c.get("name") == chat_name:
            existing_chat = c
            break

    if mode == "new" or existing_chat is None:
        original_name = chat_name
        counter = 1
        while any(c.get("name") == chat_name for c in mgr.data.get("chats", [])):
            chat_name = f"{original_name} ({counter})"
            counter += 1

        result = mgr.create_chat(password, chat_name)
        if result is None:
            return jsonify({"error": "Chat creation failed"}), 502

        for c in mgr.data.get("chats", []):
            if c.get("name") == chat_name:
                existing_chat = c
                break

    if existing_chat is None:
        return jsonify({"error": "Could not find or create chat"}), 502

    enc_key = mgr.decrypt_chat_key(chat_name, password)
    if enc_key is None:
        return jsonify({"error": "Could not decrypt chat key"}), 502

    from cryptohelper import encrypt_message

    imported_count = 0
    for msg in messages:
        content = msg.get("content", "")
        msg_type = msg.get("type", "text")
        direction = msg.get("direction", "incoming")
        filename = msg.get("filename", "")

        if msg_type == "media" and filename:
            if not content.startswith("[MEDIA:"):
                content = f"[MEDIA:{filename}]{content}"

        try:
            encrypted = encrypt_message(
                enc_key, existing_chat["routekey"], existing_chat["route"], content
            )
            is_outgoing = 1 if direction == "outgoing" else 0
            existing_chat["messages"].append((encrypted, is_outgoing))
            imported_count += 1
        except Exception as e:
            print(f"Error importing message: {e}")

    mgr.save_config()

    return jsonify({
        "status": "ok",
        "chat_name": chat_name,
        "imported": imported_count,
        "total": len(messages)
    }), 200


def main():
    app.run(debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
