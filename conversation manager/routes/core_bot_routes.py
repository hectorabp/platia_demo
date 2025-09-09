from flask import Blueprint, request, jsonify
import json
import sys
from pathlib import Path
from datetime import datetime
from bson.objectid import ObjectId

# Asegurar que el directorio 'backend' esté en sys.path para poder importar controller
sys.path.append(str(Path(__file__).resolve().parent.parent))

from controller.core_bot import CoreBot

bp = Blueprint('core_bot', __name__)
bot = CoreBot()


"""
Rutas del CoreBot

Endpoints disponibles:

- POST /api/process_message
    - Descripción: Procesa un mensaje entrante para un transmitter (phone/email/chat/meta).
    - Payload (JSON):
        {
            "content": {"role": "user|bot", "text": "..."},
            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "send_data": {"audio": null, "image": null, "location": null, "document": null, "video": null},
            "phone": "+549...", "email": "x@x.com", "chat_id": "...", "meta_id": "..."
        }
    - Respuesta JSON: {"success": True|False, "session_id": "...", "created": True|False, "conversation": {...}}

- GET /api/conversations/<id_type>/<value>
    - Descripción: Retorna todas las conversaciones cuyo campo `transmitter` coincide exactamente con `value`.
    - id_type: one of `phone`, `email`, `chat`, `meta`.
    - Respuesta JSON: {"success": True, "conversations": [doc,...]}

- GET /api/conversation/<session_id>
    - Descripción: Retorna el documento de conversación completo para `session_id`.
    - Respuesta: 200 con {"success": True, "conversation": doc} o 404 si no existe.

- POST /api/state
    - Descripción: Inserta o reemplaza un estado (state) en la conversación.
    - Payload: {"session_id": "...", "state": {"name": "state_name", "value": ...}}
    - Respuesta: {"success": True|False}

- DELETE /api/state
    - Descripción: Elimina un estado por nombre.
    - Payload: {"session_id": "...", "state_name": "..."}
    - Respuesta: {"success": True|False}

- GET /api/transmitter/sessions/<id_type>/<value>
    - Descripción: Lista sesiones registradas para un transmitter (últimas primero si las hay).
    - Respuesta: {"success": True, "sessions": [{"session_id":"...","timestamp":"ISO"}, ...]}

Notas:
- Todos los endpoints devuelven JSON.
- Los identificadores de transmitter (phone/email/chat/meta) son usados tal cual se almacenan en los documentos.
"""


@bp.route('/process_message', methods=['POST'])
def process_message():
    data = request.get_json() or {}
    content = data.get('content')
    # Normalizar `content` a dict:
    # - si viene como string, intentar parsear JSON (p. ej. "{\"role\":\"user\",\"text\":\"...\"}")
    # - si el parseo falla, envolverlo como {"text": <string>} para mantener consistencia
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                content = parsed
            else:
                content = {"text": str(content)}
        except Exception:
            content = {"text": content}
    if content is None:
        return jsonify({"success": False, "error": "missing content"}), 400
    if not isinstance(content, dict):
        return jsonify({"success": False, "error": "content must be object or JSON string"}), 400
    # Normalizar `tokens` (puede venir como JSON string desde integraciones como n8n)
    tokens_raw = data.get('tokens')
    tokens_default = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if isinstance(tokens_raw, str):
        try:
            parsed = json.loads(tokens_raw)
            tokens = parsed if isinstance(parsed, dict) else tokens_default
        except Exception:
            tokens = tokens_default
    elif isinstance(tokens_raw, dict):
        tokens = tokens_raw
    else:
        tokens = tokens_default
    send_raw = data.get('send_data')
    send_default = {"audio": None, "image": None, "location": None, "document": None, "video": None}
    if isinstance(send_raw, str):
        try:
            parsed = json.loads(send_raw)
            send_data = parsed if isinstance(parsed, dict) else send_default
        except Exception:
            send_data = send_default
    elif isinstance(send_raw, dict):
        send_data = send_raw
    else:
        send_data = send_default
    phone = data.get('phone')
    email = data.get('email')
    chat_id = data.get('chat_id')
    meta_id = data.get('meta_id')

    result = bot.process_message(content, tokens, send_data, phone=phone, email=email, chat_id=chat_id, meta_id=meta_id)
    # Serializar objetos no JSON-serializables (ObjectId, datetime) recursivamente
    def _serialize(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            try:
                return obj.isoformat()
            except Exception:
                return str(obj)
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serialize(v) for v in obj]
        return obj

    safe_result = _serialize(result)
    return jsonify(safe_result)


@bp.route('/conversations/<id_type>/<value>', methods=['GET'])
def conversations_by(id_type, value):
    mapping = {
        'phone': bot.get_conversations_by_phone,
        'email': bot.get_conversations_by_email,
        'chat': bot.get_conversations_by_chat_id,
        'meta': bot.get_conversations_by_meta_id
    }
    func = mapping.get(id_type)
    if not func:
        return jsonify({"ok": False, "error": "invalid id_type"}), 400
    docs = func(value)
    # serializar _id a str si existe
    safe_docs = []
    for d in docs:
        if isinstance(d, dict) and '_id' in d:
            d = d.copy()
            d['_id'] = str(d['_id'])
        safe_docs.append(d)
    return jsonify({"ok": True, "conversations": safe_docs})


@bp.route('/conversation/<session_id>', methods=['GET'])
def get_conversation(session_id):
    convo = bot.conversation_module.get_conversation(session_id)
    if not convo:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if '_id' in convo:
        convo = convo.copy()
        convo['_id'] = str(convo['_id'])
    return jsonify({"ok": True, "conversation": convo})


@bp.route('/state', methods=['POST'])
def add_state():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    state = data.get('state')
    if not session_id or not isinstance(state, dict):
        return jsonify({"ok": False, "error": "missing session_id or state"}), 400
    ok = bot.add_or_replace_state(session_id, state)
    return jsonify({"ok": ok})


@bp.route('/state', methods=['DELETE'])
def delete_state():
    data = request.get_json() or {}
    session_id = data.get('session_id')
    state_name = data.get('state_name')
    if not session_id or not state_name:
        return jsonify({"ok": False, "error": "missing session_id or state_name"}), 400
    ok = bot.remove_state(session_id, state_name)
    return jsonify({"ok": ok})


@bp.route('/transmitter/sessions/<id_type>/<value>', methods=['GET'])
def transmitter_sessions(id_type, value):
    mapping = {
        'phone': bot.transmitter_module.get_sessions_by_phone,
        'email': bot.transmitter_module.get_sessions_by_email,
        'chat': bot.transmitter_module.get_sessions_by_chat_id,
        'meta': bot.transmitter_module.get_sessions_by_meta_id
    }
    func = mapping.get(id_type)
    if not func:
        return jsonify({"ok": False, "error": "invalid id_type"}), 400
    sessions = func(value)
    return jsonify({"ok": True, "sessions": sessions})
