from flask import Flask
from api import api_bp  # Import the API blueprint

app = Flask(__name__)

# Register the API blueprint
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/')
def home():
    return "Spese-ms is up and running!"