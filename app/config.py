import os
from datetime import timedelta


class Config:
    """Base configuration class"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)

    # Upload folder
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')

    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

    # Ngrok
    NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')
    ENABLE_NGROK = os.getenv('ENABLE_NGROK', '0')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///lunch_app.db')
    JWT_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = 'None'


class TestConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_COOKIE_SECURE = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'test': TestConfig,
    'default': DevelopmentConfig
}

