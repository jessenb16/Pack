import os 

class Config:
    SECRET_KEY = 'your_secret_key'
    # Other common configurations

class OthersConfig(Config):
    DATABASE_PORT = 8889
    DB_USER = 'root'
    DB_PASSWORD = 'root'
    DB_NAME = 'Pack'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3'}