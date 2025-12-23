import logging
from fastapi import FastAPI
from pymongo import MongoClient
from urllib.parse import quote_plus

from app.core import config

logger = logging.getLogger(__name__)


def connect_database(app: FastAPI) -> None:
    logger.info('Connecting to database...')
    db_uri = f'mongodb+srv://{config.DB_USER}:{quote_plus(config.DB_PASS)}@{config.DB_HOST}/{config.DB_NAME}?retryWrites=true&w=majority'
    mongo_client = MongoClient(db_uri)
    app.state.database = mongo_client[config.DB_NAME]
    logger.info('Connected to database!')


def disconnect_database(app: FastAPI) -> None:
    logger.info('Disconnecting database...')
    app.state.database.client.close()
    logger.info('Database disconnected!')
