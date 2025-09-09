# core_bot.py
from typing import Callable, Dict, Any, Optional, List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from modules.conversation import Conversation  
from modules.transmitter import Transmitter

class CoreBot:
    """
    CoreBot: orquesta la conversación, persiste con Conversation (Mongo) y enruta a handlers/flows.
    """
    def __init__(self):
        self.conversation_module = Conversation()
        self.transmitter_module = Transmitter()

    # ----------------- utilitarios -----------------
    def _pick_primary_identifier(self, phone: Optional[str], email: Optional[str], chat_id: Optional[str], meta_id: Optional[str]) -> Optional[str]:
        """Devuelve el primer identificador no vacío en el orden: phone, email, chat_id, meta_id."""
        for v in (phone, email, chat_id, meta_id):
            if v and str(v).strip():
                return str(v).strip()
        return None

    def _is_timestamp_within_24h(self, iso_ts: str) -> bool:
        from datetime import datetime, timezone, timedelta
        try:
            ts = datetime.fromisoformat(iso_ts)
            # asegurar tz-aware
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - ts) < timedelta(hours=24)
        except Exception:
            return False

    # ----------------- flujo principal -----------------
    def process_message(self, content: Dict[str, Any], tokens: Dict[str, int], send_data: Dict[str, Any], phone: Optional[str] = None, email: Optional[str] = None, chat_id: Optional[str] = None, meta_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Lógica principal: determina la sesión vigente para el transmitter (si existe y <24h) y:
        - Si no existe sesión activa -> crea nueva sesión en `conversation` y la registra en `transmitter`.
        - Si existe sesión activa -> inserta el mensaje en la conversación existente.

        Siempre devuelve el historial (documento de conversation) de la sesión usada.
        Retorna dict con keys: 'success', 'session_id', 'created', 'conversation' (documento o None), 'error'
        """
        primary = self._pick_primary_identifier(phone, email, chat_id, meta_id)
        if primary is None:
            return {"success": False, "error": "No transmitter identifier provided"}

        # Obtener la última sesión conocida para el identificador
        sessions = []
        try:
            if phone and phone.strip():
                sessions = self.transmitter_module.get_sessions_by_phone(phone, limit=1, newest_first=True)
            elif email and email.strip():
                sessions = self.transmitter_module.get_sessions_by_email(email, limit=1, newest_first=True)
            elif chat_id and chat_id.strip():
                sessions = self.transmitter_module.get_sessions_by_chat_id(chat_id, limit=1, newest_first=True)
            elif meta_id and meta_id.strip():
                sessions = self.transmitter_module.get_sessions_by_meta_id(meta_id, limit=1, newest_first=True)
        except Exception:
            sessions = []

        latest_session = sessions[0] if sessions else None

        # si hay sesión y está activa (<24h) usamos esa
        if latest_session and self._is_timestamp_within_24h(latest_session.get("timestamp", "")):
            session_id = latest_session.get("session_id")
            # insertar mensaje en conversation
            res = self.conversation_module.add_message(session_id, content, tokens, send_data)
            convo = self.conversation_module.get_conversation(session_id, transmitter=primary)
            return {"success": True, "session_id": session_id, "created": False, "conversation": convo}

        # Si no hay sesión o la última expiró -> crear nueva sesión
        new_conv = self.conversation_module.new_conversation(content, tokens, send_data, transmitter=primary)
        if not new_conv:
            return {"success": False, "error": "failed to create conversation"}

        new_session_id = new_conv.get("session_id")
        # registrar sesión en transmitter (upsert)
        try:
            added = self.transmitter_module.add_session(new_session_id, phone=phone, email=email, chat_id=chat_id, meta_id=meta_id)
        except Exception:
            added = False

        convo = self.conversation_module.get_conversation(new_session_id, transmitter=primary)
        return {"success": True, "session_id": new_session_id, "created": True, "transmitter_registered": added, "conversation": convo}

    # ----------------- consultas simples -----------------
    def get_conversations_by_transmitter_value(self, transmitter_value: str) -> List[Dict[str, Any]]:
        """Retorna todas las conversaciones cuyo campo `transmitter` es exactamente `transmitter_value`."""
        if not transmitter_value:
            return []
        try:
            docs = list(self.conversation_module.collection.find({"transmitter": transmitter_value}))
            return docs
        except Exception:
            return []

    def get_conversations_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        return self.get_conversations_by_transmitter_value(phone)

    def get_conversations_by_email(self, email: str) -> List[Dict[str, Any]]:
        return self.get_conversations_by_transmitter_value(email)

    def get_conversations_by_chat_id(self, chat_id: str) -> List[Dict[str, Any]]:
        return self.get_conversations_by_transmitter_value(chat_id)

    def get_conversations_by_meta_id(self, meta_id: str) -> List[Dict[str, Any]]:
        return self.get_conversations_by_transmitter_value(meta_id)

    # ----------------- manejo de estados (states) -----------------
    def add_or_replace_state(self, session_id: str, new_state: Dict[str, Any]) -> bool:
        """
        Inserta un nuevo estado o reemplaza si ya existe un estado con el mismo `name`.
        new_state debe contener al menos {'name': ..., 'value': ...}
        """
        if not session_id or not isinstance(new_state, dict) or 'name' not in new_state:
            return False
        name = new_state['name']
        value = new_state.get('value')
        # intentar sobrescribir
        try:
            replaced = self.conversation_module.overwrite_state(session_id, name, value)
            if replaced:
                return True
            # si no existía, agregar
            return self.conversation_module.add_state(session_id, new_state)
        except Exception:
            return False

    def remove_state(self, session_id: str, state_name: str) -> bool:
        """Elimina un estado por nombre del documento de conversación."""
        if not session_id or not state_name:
            return False
        try:
            res = self.conversation_module.collection.update_one({"session_id": session_id}, {"$pull": {"state": {"name": state_name}}})
            return res.modified_count > 0
        except Exception:
            return False
