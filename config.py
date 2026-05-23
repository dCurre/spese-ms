import os

from flask.cli import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

# Load .env only in local development (not on Vercel or other cloud platforms)
if not os.environ.get("VERCEL") and not os.environ.get("RENDER"):
    load_dotenv()

class Config:
    db_host = os.environ.get('DATASOURCE_URL')
    db_port = os.environ.get('DATASOURCE_PORT')
    db_name = os.environ.get('DATASOURCE_DB_NAME')
    db_user = os.environ.get('DATASOURCE_USERNAME')
    db_password = os.environ.get('DATASOURCE_PASSWORD')
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Serverless-friendly pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 2,
    }
