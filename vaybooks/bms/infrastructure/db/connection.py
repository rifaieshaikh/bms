import os

import streamlit as st
from pymongo import MongoClient


def _mongo_uri() -> str:
    return os.environ.get("MONGODB_URI") or st.secrets["MONGODB_URI"]


def _mongo_database() -> str:
    return os.environ.get("MONGODB_DATABASE") or st.secrets["MONGODB_DATABASE"]


@st.cache_resource
def get_mongo_client():
    """A single MongoClient shared across all sessions and reruns.

    st.cache_resource guarantees one instance per Streamlit process, so we no
    longer open a new connection pool on every rerun. MongoClient is
    thread-safe, so sharing it is safe.
    """
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
