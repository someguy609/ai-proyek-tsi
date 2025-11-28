import logging
from fastapi import FastAPI
from pymongo import MongoClient
from urllib.parse import quote_plus

from app.core import config


def connect_database(app: FastAPI) -> None:
    print('Connecting to database...')
    db_uri = f'mongodb+srv://{config.DB_USER}:{quote_plus(config.DB_PASS)}@{config.DB_HOST}/{config.DB_NAME}?retryWrites=true&w=majority'
    mongo_client = MongoClient(db_uri)
    app.state.database = mongo_client[config.DB_NAME]
    print('Connected to database!')


def disconnect_database(app: FastAPI) -> None:
    print('Disconnecting database...')
    app.state.database.client.close()
    print('Database disconnected!')
