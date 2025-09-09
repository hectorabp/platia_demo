from flask import Flask
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from routes.core_bot_routes import bp as core_bp


app = Flask(__name__)
app.register_blueprint(core_bp, url_prefix='/api')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
