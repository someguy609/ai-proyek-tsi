import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv('APP_NAME', 'APP_NAME')
APP_HOST = os.getenv('APP_HOST', '0.0.0.0')
APP_PORT = int(os.getenv('APP_PORT', '8080'))
DEBUG = bool(os.getenv('DEBUG', 'False'))

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME')

MODEL_PATH = os.getenv('MODEL_PATH', 'yolov11m.pt')
MODEL_SOURCE = os.getenv('MODEL_SOURCE', '').split(',')

CORS_ALLOW_ORIGINS = os.getenv('CORS_ALLOW_ORIGINS', '*')
CORS_ALLOW_METHODS = os.getenv('CORS_ALLOW_METHODS', '*')
CORS_ALLOW_HEADERS = os.getenv('CORS_ALLOW_HEADERS', '*')
CORS_ALLOW_CREDENTIALS = bool(os.getenv('CORS_ALLOW_CREDENTIALS', 'True'))
