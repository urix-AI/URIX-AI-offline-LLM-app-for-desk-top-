# urix/utils/database.py

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class KnowledgeBase:
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._setup_database()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _setup_database(self):
        try:
            conn = self._connect()
            cursor = conn.cursor()
            # Table for Q&A history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY,
                    question TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            # --- NEW: Table for the user's personal profile ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"Database setup complete at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to set up database: {e}", exc_info=True)

    def add_entry(self, question: str, answer: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO knowledge_base (question, answer, timestamp)
                VALUES (?, ?, ?)
            """, (question.strip(), answer.strip(), timestamp))
            conn.commit()
            conn.close()
            logger.info(f"Added/Updated entry for question: '{question[:50]}...'")
        except Exception as e:
            logger.error(f"Failed to add entry to knowledge base: {e}", exc_info=True)

    def get_answer(self, question: str) -> Optional[str]:
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT answer FROM knowledge_base WHERE question = ?", (question.strip(),))
            result = cursor.fetchone()
            conn.close()
            if result:
                logger.info(f"Found answer in knowledge base for: '{question[:50]}...'")
                return result[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve answer from knowledge base: {e}", exc_info=True)
            return None

    # --- NEW: Function to save a user preference ---
    def set_profile_setting(self, key: str, value: str):
        """Saves or updates a key-value pair in the user_profile table."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)", (key.strip(), value.strip()))
            conn.commit()
            conn.close()
            logger.info(f"Set profile setting: {key} = {value}")
        except Exception as e:
            logger.error(f"Failed to set profile setting: {e}", exc_info=True)

    # --- NEW: Function to load the entire user profile ---
    def get_full_profile(self) -> Dict[str, str]:
        """Retrieves the entire user profile as a dictionary."""
        profile = {}
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_profile")
            results = cursor.fetchall()
            conn.close()
            for key, value in results:
                profile[key] = value
            logger.info("Loaded user profile from database.")
        except Exception as e:
            logger.error(f"Failed to get full profile: {e}", exc_info=True)
        return profile  