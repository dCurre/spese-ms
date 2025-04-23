print("DAVIDE Loading app.py file")

import os
import logging
from flask import Flask

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return "Hello from Flask on Render!"

print(f"__name__ is: {__name__}")
logger.info(f"__name__ is: {__name__}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 for local testing
    app.run(host='0.0.0.0', port=port)