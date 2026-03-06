import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

    # Database
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'data', 'kanban.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Application
    APP_NAME = os.getenv('APP_NAME', 'Kanban Board')
    MAX_USERS = int(os.getenv('MAX_USERS', 10))
    PORT = int(os.getenv('PORT', 3000))
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
