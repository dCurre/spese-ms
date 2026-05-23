import sys
import os

# Assicura che la root del progetto sia nel path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()
