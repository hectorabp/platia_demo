from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from configs.config import Database_conversation


class Transmitter:
    """
    Gestiona documentos que agrupan identificadores de transmitter
    y una lista ordenada de sesiones asociadas a ese transmitter.

    Documento esperado (campo `transmitter`):
    {
        "transmitter": {
            "phone": "",
            "email": "",
            "chat_id": "",
            "meta_id": "",
            "sessions": [ {"session_id": "", "timestamp": "ISO"}, ... ]
        }
    }

    Reglas principales:
    - Al crear/actualizar debe haber al menos un identificador no vacío
      entre phone, email, chat_id y meta_id.
    - Se ofrecen métodos para agregar sesiones y recuperar sesiones
      filtrando por phone/email/chat_id/meta_id de forma ordenada.
    """

    def __init__(self, db_manager: Optional[Database_conversation] = None):
        self.db_manager = db_manager or Database_conversation()
        self.db_manager.connect()
        self.collection: Collection = self.db_manager.get_collection("transmitter_sessions")

    # ----------------- utilitarios -----------------
    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _has_any_identifier(phone: Optional[str], email: Optional[str], chat_id: Optional[str], meta_id: Optional[str]) -> bool:
        return bool((phone and phone.strip()) or (email and email.strip()) or (chat_id and chat_id.strip()) or (meta_id and meta_id.strip()))

    def _build_transmitter_doc(self, phone: Optional[str], email: Optional[str], chat_id: Optional[str], meta_id: Optional[str]) -> Dict[str, Any]:
        return {
            "transmitter": {
                "phone": phone or "",
                "email": email or "",
                "chat_id": chat_id or "",
                "meta_id": meta_id or "",
                "sessions": []
            }
        }

    # ----------------- operaciones CRUD/logic -----------------
    def ensure_transmitter(self, phone: Optional[str] = None, email: Optional[str] = None, chat_id: Optional[str] = None, meta_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Asegura que exista un documento transmitter para los identificadores dados.
        Devuelve el documento actual o None en error.
        """
        if not self._has_any_identifier(phone, email, chat_id, meta_id):
            return None

        # Construir filtro: buscar por cualquiera de los identificadores no vacíos
        or_clauses = []
        if phone and phone.strip():
            or_clauses.append({"transmitter.phone": phone})
        if email and email.strip():
            or_clauses.append({"transmitter.email": email})
        if chat_id and chat_id.strip():
            or_clauses.append({"transmitter.chat_id": chat_id})
        if meta_id and meta_id.strip():
            or_clauses.append({"transmitter.meta_id": meta_id})

        filter_query = {"$or": or_clauses} if len(or_clauses) > 1 else or_clauses[0]

        try:
            # Si existe, retornarlo; si no existe, insertarlo con upsert
            update = {
                "$setOnInsert": self._build_transmitter_doc(phone, email, chat_id, meta_id)["transmitter"]
            }
            # upsert and return the document
            result = self.collection.find_one_and_update(filter_query, {"$setOnInsert": update["$setOnInsert"]}, upsert=True, return_document=True)
            # find_one_and_update puede retornar None según driver; buscar luego si es None
            if result is None:
                result = self.collection.find_one(filter_query)
            return result
        except PyMongoError:
            return None

    def add_session(self, session_id: str, phone: Optional[str] = None, email: Optional[str] = None, chat_id: Optional[str] = None, meta_id: Optional[str] = None) -> bool:
        """
        Agrega una entrada de sesión (session_id + timestamp) al documento transmitter que coincida
        con cualquiera de los identificadores proporcionados. Si no existe, crea el documento.
        Retorna True si la operación tuvo éxito.
        """
        if not session_id:
            return False
        if not self._has_any_identifier(phone, email, chat_id, meta_id):
            return False

        ts = self._now_iso()
        session_entry = {"session_id": session_id, "timestamp": ts}

        # preparar filtro similar a ensure_transmitter
        or_clauses = []
        if phone and phone.strip():
            or_clauses.append({"transmitter.phone": phone})
        if email and email.strip():
            or_clauses.append({"transmitter.email": email})
        if chat_id and chat_id.strip():
            or_clauses.append({"transmitter.chat_id": chat_id})
        if meta_id and meta_id.strip():
            or_clauses.append({"transmitter.meta_id": meta_id})

        filter_query = {"$or": or_clauses} if len(or_clauses) > 1 else or_clauses[0]

        # prepare setOnInsert to keep provided ids on create
        set_on_insert = {}
        if phone and phone.strip():
            set_on_insert["transmitter.phone"] = phone
        if email and email.strip():
            set_on_insert["transmitter.email"] = email
        if chat_id and chat_id.strip():
            set_on_insert["transmitter.chat_id"] = chat_id
        if meta_id and meta_id.strip():
            set_on_insert["transmitter.meta_id"] = meta_id

        update = {"$push": {"transmitter.sessions": session_entry}}
        if set_on_insert:
            update["$setOnInsert"] = set_on_insert

        try:
            res = self.collection.update_one(filter_query, update, upsert=True)
            return res.acknowledged
        except PyMongoError:
            return False

    # ----------------- consultas específicas -----------------
    def get_sessions_by_phone(self, phone: str, limit: Optional[int] = None, newest_first: bool = True) -> List[Dict[str, str]]:
        if not phone:
            return []
        try:
            docs = list(self.collection.find({"transmitter.phone": phone}))
            sessions: List[Dict[str, str]] = []
            for d in docs:
                s = d.get("transmitter", {}).get("sessions", [])
                sessions.extend(s)
            sessions_sorted = sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=newest_first)
            return sessions_sorted[:limit] if limit else sessions_sorted
        except PyMongoError:
            return []

    def get_sessions_by_email(self, email: str, limit: Optional[int] = None, newest_first: bool = True) -> List[Dict[str, str]]:
        if not email:
            return []
        try:
            docs = list(self.collection.find({"transmitter.email": email}))
            sessions: List[Dict[str, str]] = []
            for d in docs:
                s = d.get("transmitter", {}).get("sessions", [])
                sessions.extend(s)
            sessions_sorted = sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=newest_first)
            return sessions_sorted[:limit] if limit else sessions_sorted
        except PyMongoError:
            return []

    def get_sessions_by_chat_id(self, chat_id: str, limit: Optional[int] = None, newest_first: bool = True) -> List[Dict[str, str]]:
        if not chat_id:
            return []
        try:
            docs = list(self.collection.find({"transmitter.chat_id": chat_id}))
            sessions: List[Dict[str, str]] = []
            for d in docs:
                s = d.get("transmitter", {}).get("sessions", [])
                sessions.extend(s)
            sessions_sorted = sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=newest_first)
            return sessions_sorted[:limit] if limit else sessions_sorted
        except PyMongoError:
            return []

    def get_sessions_by_meta_id(self, meta_id: str, limit: Optional[int] = None, newest_first: bool = True) -> List[Dict[str, str]]:
        if not meta_id:
            return []
        try:
            docs = list(self.collection.find({"transmitter.meta_id": meta_id}))
            sessions: List[Dict[str, str]] = []
            for d in docs:
                s = d.get("transmitter", {}).get("sessions", [])
                sessions.extend(s)
            sessions_sorted = sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=newest_first)
            return sessions_sorted[:limit] if limit else sessions_sorted
        except PyMongoError:
            return []
