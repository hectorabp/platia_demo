from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError  
from dotenv import load_dotenv
import os

load_dotenv()

class Database_conversation:
    def __init__(self,):
        """
        Inicializa el gestor de conexión a MongoDB.
        """
        self.host = os.getenv('DB_MONGO_HOST')
        self.db_name = os.getenv('DB_MONGO_NAME')
        self.user = os.getenv('DB_MONGO_USER')
        self.password = os.getenv('DB_MONGO_PASS')
        self.client = None
        self.db = None
        self.uri = f"mongodb://{self.user}:{self.password}@{self.host}:27017/{self.db_name}?authSource=admin"

    def connect(self):
        """
        Conecta a la base de datos de MongoDB especificada.
        """
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.db_name]
        except ServerSelectionTimeoutError  as e:
            print(f"[ERROR_DATABASE_CONVERSATION]: Error al conectar a MongoDB: {e}")
            raise

    def close_connection(self):
        """
        Cierra la conexión a la base de datos de MongoDB.
        """
        if self.client:
            self.client.close()
        else:
            print("[DATABASE_CONVERSATION]: No hay conexión activa a MongoDB.")

    def get_collection(self, collection_name: str):
        """
        Obtiene una colección de la base de datos.
        
        :param collection_name: Nombre de la colección.
        :return: Colección de MongoDB.
        """
        if self.db is not None:
            return self.db[collection_name]
        else:
            raise RuntimeError("[ERROR_DATABASE_CONVERSATION]: No hay conexión activa a la base de datos. Conéctese primero.")

