"""
Database Service

MongoDB connection and management for the Shariaa Contract Analyzer.
"""

import logging
from pymongo import MongoClient
from flask import current_app

logger = logging.getLogger(__name__)

# Global database connections
client = None
db = None
contracts_collection = None
terms_collection = None
expert_feedback_collection = None

DB_NAME = "shariaa_analyzer_db"


def init_db(app):
    """Initialize database connection."""
    global client, db, contracts_collection, terms_collection, expert_feedback_collection
    
    try:
        mongo_uri = app.config.get('MONGO_URI')
        if not mongo_uri:
            logger.warning("MONGO_URI not configured - database services will be unavailable")
            return
            
        logger.info("Attempting to connect to MongoDB...")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=45000)
        client.admin.command('ping')
        db = client[DB_NAME]
        contracts_collection = db.contracts
        terms_collection = db.terms
        expert_feedback_collection = db.expert_feedback
        logger.info(f"Successfully connected to MongoDB: {DB_NAME}")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        logger.warning("Database services will be unavailable")
        # Set collections to None so endpoints can handle gracefully
        client = None
        db = None
        contracts_collection = None
        terms_collection = None
        expert_feedback_collection = None


def get_contracts_collection():
    """Get contracts collection."""
    return contracts_collection


def get_terms_collection():
    """Get terms collection."""
    return terms_collection


def get_expert_feedback_collection():
    """Get expert feedback collection."""
    return expert_feedback_collection