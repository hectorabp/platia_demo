import nltk
from nltk.tokenize import word_tokenize
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from datetime import datetime, timezone
import time
import random
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from configs.config import Database_conversation
class Conversation:
    def __init__(self):
        """
        Inicializa el gestor CRUD para la colección 'conversation'.

        :param db_manager: Instancia de MongoDBConnectionManager para la conexión a MongoDB.
        """
        self.db_manager = Database_conversation()
        self.db_manager.connect() 
        self.collection: Collection = self.db_manager.get_collection("conversation")

    def new_conversation(self, content, tokens, send_data, transmitter: str = None):
        """
        Crea un nuevo documento de conversación en la colección 'conversation'.

        :param conversation_data: Diccionario con los datos de la conversación.
        :return: Diccionario con session_id y inserted_id (ObjectId).
        """
        try:
            # hora del mensaje y marca de creación de la sesión (ISO UTC)
            hour = datetime.now(timezone.utc).strftime('%H:%M:%S')
            created_at = datetime.now(timezone.utc).isoformat()
            session_id = self.generate_id()
            message_id = self.generate_id()
            conversation_data = {
                "session_id": session_id,
                "state": [],
                # opcional: desde donde vino el mensaje (p.ej. 'phone','chat','meta','bot')
                "transmitter": transmitter,
                # timestamp de creación de la sesión
                "created_at": created_at,
                "message": [{
                    "message_id" : message_id,
                    "role": content['role'],
                    "tokens": {
                        "prompt_tokens":tokens["prompt_tokens"],
                        "completion_tokens":tokens["completion_tokens"],
                        "total_tokens":tokens["total_tokens"]
                    },
                    "content": content['text'],
                    "send": {
                        "audio": send_data["audio"],
                        "image": send_data["image"],
                        "location": send_data["location"],
                        "document": send_data["document"],
                        "video": send_data["video"]
                    },
                    "hour": hour
                }]
            }
            result = self.collection.insert_one(conversation_data)
            print(f"[CREANDO_CONVERSACION]: {conversation_data}")
            # Ahora devolvemos: session_id, inserted_id y metadatos
            return {"session_id": session_id, "inserted_id": str(result.inserted_id), "transmitter": transmitter, "created_at": created_at}
        except PyMongoError as e:
            print(f"Error al crear la conversación: {e}")
            return None
        
    def add_message(self, session_id, content, tokens, send_data):
        """
        Agrega un nuevo mensaje a la conversación existente según el ID de sesión.

        :param session_id: ID de la sesión.
        :param content: Contenido del mensaje.
        :param tokens: Tokens asociados al mensaje.
        :param send_data: Datos adicionales a enviar.
        """
        try:
            message_id = self.generate_id()
            hour = datetime.now(timezone.utc).strftime('%H:%M:%S')
            # Construir la estructura de la sesión
            message_entry = {
                    "message_id" : message_id,
                    "role": content['role'],
                    "tokens": {
                        "prompt_tokens":tokens["prompt_tokens"],
                        "completion_tokens":tokens["completion_tokens"],
                        "total_tokens":tokens["total_tokens"]
                    },
                    "content": content['text'],
                    "send": {
                        "audio": send_data["audio"],
                        "image": send_data["image"],
                        "location": send_data["location"],
                        "document": send_data["document"],
                        "video": send_data["video"]
                    },
                    "hour": hour
                }

            # Actualizar o crear el documento (filtro simplificado)
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$push": {"message": message_entry}},
                upsert=True
            )
            return result
        except PyMongoError as e:
            print(f"[ERROR_ADD_SESSION]: Error al agregar la nueva sesión: {e}")
            return False

    def generate_id(self):
        timestamp = int(time.time() * 1000) 
        random_suffix = random.randint(1000, 9999)
        return f"{timestamp}{random_suffix}"

    def get_conversation_by_session_id(self, session_id, transmitter: str = None):
        """
        Obtiene todas las conversaciones asociadas a un ID de sesión.

        :param session_id: ID de la sesión.
        :return: Lista de conversaciones o una lista vacía si no se encuentran conversaciones.
        """
        try:
            query = {"session_id": session_id}
            if transmitter is not None:
                query["transmitter"] = transmitter
            conversations = list(self.collection.find(query))
            return conversations
        except PyMongoError as e:
            return []

    def get_conversation(self, session_id, transmitter: str = None):
        """
        Devuelve un único documento de conversación por session_id (opcionalmente filtrando por transmitter).
        """
        try:
            docs = self.get_conversation_by_session_id(session_id, transmitter=transmitter)
            return docs[0] if docs else None
        except PyMongoError:
            return None

    def add_state(self, session_id, new_state):
        """
        Actualiza el array 'state' en un documento de conversación agregando nuevos estados.

        :param new_state: El nuevo estado a agregar.
        :return: True si la actualización fue exitosa, False en caso contrario.
        """
        try:
            # Agregar el nuevo estado al array 'state' sin sobrescribir los existentes
            # SUGERENCIA: Para acceso rápido, podrías mantener un diccionario adicional 'states' en el documento:
            # self.collection.update_one({"session_id": session_id}, {"$set": {f"states.{new_state['name']}": new_state['value']}})
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$push": {"state": new_state}}
            )
            if result.matched_count > 0:
                return True
            else:
                return False
        except PyMongoError as e:
            return False

    def overwrite_state(self, session_id, state_name, state_value):
        """
        Sobrescribe el valor de un estado existente en la conversación.

        :param state_name: Nombre del estado a sobrescribir.
        :param state_value: Nuevo valor del estado.
        :return: True si la actualización fue exitosa, False en caso contrario.
        """
        try:
            # Sobrescribe el valor del estado en el array 'state'
            result = self.collection.update_one(
                {"session_id": session_id, "state.name": state_name},
                {"$set": {"state.$.value": state_value}}  # Sobrescribe el valor del estado
            )
            if result.matched_count > 0:
                return True
            else:
                return False
        except PyMongoError as e:
            return False

    def update_conversation(self, session_id, update_data):
        """
        Actualiza un documento de conversación por su ID.

        :param conversation_id: ID del documento de la conversación.
        :param update_data: Diccionario con los datos a actualizar.
        :return: True si la actualización fue exitosa, False en caso contrario.
        """
        try:
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": update_data}
            )
            if result.matched_count > 0:
                return True
            else:
                return False
        except PyMongoError as e:
            return False

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Elimina un documento de conversación por su ID.

        :param conversation_id: ID del documento de la conversación.
        :return: True si la eliminación fue exitosa, False en caso contrario.
        """
        try:
            result = self.collection.delete_one({"_id": ObjectId(conversation_id)})
            if result.deleted_count > 0:
                return True
            else:
                return False
        except PyMongoError as e:
            return False