# wsgi.py
from app import create_app

print("Creating Flask app...")  # DEBUG line
app = create_app()
print("App created.")           # DEBUG line