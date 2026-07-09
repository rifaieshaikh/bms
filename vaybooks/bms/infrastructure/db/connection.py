import os

import streamlit as st
from pymongo import MongoClient

from vaybooks.bms.infrastructure.config.settings import get_settings, validate_mongo_connection


def _mongo_uri() -> str:
    settings = get_settings()
    if settings.mongo_uri:
        return settings.mongo_uri
    return os.environ.get("MONGODB_URI") or st.secrets["MONGODB_URI"]


def _mongo_database() -> str:
    settings = get_settings()
    if settings.db_name:
        return settings.db_name
    return os.environ.get("MONGODB_DATABASE") or st.secrets["MONGODB_DATABASE"]


@st.cache_resource
def get_mongo_client():
    """A single MongoClient shared across all sessions and reruns."""
    return MongoClient(
        _mongo_uri(),
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        retryWrites=True,
    )


def get_database():
    client = get_mongo_client()
    return client[_mongo_database()]


def get_database_from_uri(uri: str, database_name: str):
    """For scripts run outside Streamlit context."""
    client = MongoClient(uri)
    return client[database_name]


def get_mongo_client_from_settings():
    """Non-Streamlit MongoClient for CLI/backup scripts."""
    settings = get_settings()
    return MongoClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        retryWrites=True,
    )


__all__ = [
    "get_mongo_client",
    "get_database",
    "get_database_from_uri",
    "get_mongo_client_from_settings",
    "validate_mongo_connection",
]
