import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use PORT from Render, fallback to 5000 locally
    app.run(debug=True, host="0.0.0.0", port=port)