import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'data', 'kanban.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application
    APP_NAME = os.getenv('APP_NAME', 'Kanban Board')
    MAX_USERS = int(os.getenv('MAX_USERS', 10))
    PORT = int(os.getenv('PORT', 3000))