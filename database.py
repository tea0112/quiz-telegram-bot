"""Database management for user state and quiz tracking."""

import aiosqlite
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config import config

logger = logging.getLogger(__name__)


@dataclass
class UserState:
    """Represents a user's current state."""
    user_id: int
    username: Optional[str]
    daily_questions_completed: int
    last_daily_reset: datetime
    current_quiz_session: Optional[str]  # JSON string for current quiz state
    total_questions_answered: int
    total_correct_answers: int
    created_at: datetime
    updated_at: datetime


@dataclass
class QuizSession:
    """Represents an active quiz session."""
    session_id: str
    user_id: int
    session_type: str  # 'daily' or 'practice'
    topic: Optional[str]
    questions: List[Dict[str, Any]]  # List of question data
    current_question_index: int
    correct_answers: int
    answers_given: List[str]  # List of user's answers
    started_at: datetime
    is_completed: bool


class DatabaseManager:
    """Manages SQLite database operations for the bot."""
    
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the database and create tables."""
        try:
            # Ensure parent directory exists (important when using Docker volumes)
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await self._create_tables(db)
                await db.commit()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create necessary database tables."""
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                daily_questions_completed INTEGER DEFAULT 0,
                last_daily_reset TEXT,
                current_quiz_session TEXT,
                total_questions_answered INTEGER DEFAULT 0,
                total_correct_answers INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Quiz sessions table (for historical data)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                session_type TEXT,
                topic TEXT,
                questions_data TEXT,
                correct_answers INTEGER,
                total_questions INTEGER,
                completed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # User answers table (for detailed tracking)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT,
                question_text TEXT,
                user_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN,
                answered_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (session_id) REFERENCES quiz_sessions (session_id)
            )
        """)
    
    async def get_user_state(self, user_id: int) -> Optional[UserState]:
        """Get user state from database."""
        if not self._initialized:
            return None
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return UserState(
                    user_id=row['user_id'],
                    username=row['username'],
                    daily_questions_completed=row['daily_questions_completed'],
                    last_daily_reset=datetime.fromisoformat(row['last_daily_reset']) if row['last_daily_reset'] else datetime.now(timezone.utc),
                    current_quiz_session=row['current_quiz_session'],
                    total_questions_answered=row['total_questions_answered'],
                    total_correct_answers=row['total_correct_answers'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
                
        except Exception as e:
            logger.error(f"Failed to get user state for {user_id}: {e}")
            return None
    
    async def create_or_update_user(self, user_id: int, username: Optional[str] = None) -> bool:
        """Create a new user or update existing user information."""
        if not self._initialized:
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Check if user exists
                cursor = await db.execute(
                    "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
                )
                exists = await cursor.fetchone()
                
                if exists:
                    # Update existing user
                    await db.execute(
                        "UPDATE users SET username = ?, updated_at = ? WHERE user_id = ?",
                        (username, now, user_id)
                    )
                else:
                    # Create new user
                    await db.execute(
                        """INSERT OR IGNORE INTO users 
                           (user_id, username, daily_questions_completed, last_daily_reset, 
                            total_questions_answered, total_correct_answers, created_at, updated_at)
                           VALUES (?, ?, 0, ?, 0, 0, ?, ?)""",
                        (user_id, username, now, now, now)
                    )
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to create/update user {user_id}: {e}")
            return False
    
    async def update_daily_progress(self, user_id: int, questions_completed: int) -> bool:
        """Update user's daily progress."""
        if not self._initialized:
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """UPDATE users 
                       SET daily_questions_completed = ?, updated_at = ?
                       WHERE user_id = ?""",
                    (questions_completed, now, user_id)
                )
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update daily progress for {user_id}: {e}")
            return False
    
    async def reset_daily_progress(self, user_id: int) -> bool:
        """Reset user's daily progress (called at midnight UTC)."""
        if not self._initialized:
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """UPDATE users 
                       SET daily_questions_completed = 0, last_daily_reset = ?, updated_at = ?
                       WHERE user_id = ?""",
                    (now, now, user_id)
                )
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset daily progress for {user_id}: {e}")
            return False
    
    async def save_quiz_session(self, session: QuizSession) -> bool:
        """Save a completed quiz session."""
        if not self._initialized:
            return False
        
        try:
            import json
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO quiz_sessions 
                       (session_id, user_id, session_type, topic, questions_data, 
                        correct_answers, total_questions, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session.session_id,
                        session.user_id,
                        session.session_type,
                        session.topic,
                        json.dumps(session.questions),
                        session.correct_answers,
                        len(session.questions),
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save quiz session {session.session_id}: {e}")
            return False
    
    async def update_user_stats(self, user_id: int, questions_answered: int, correct_answers: int) -> bool:
        """Update user's overall statistics."""
        if not self._initialized:
            return False
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """UPDATE users 
                       SET total_questions_answered = total_questions_answered + ?,
                           total_correct_answers = total_correct_answers + ?,
                           updated_at = ?
                       WHERE user_id = ?""",
                    (questions_answered, correct_answers, now, user_id)
                )
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user stats for {user_id}: {e}")
            return False
    
    async def needs_daily_reset(self, user_id: int) -> bool:
        """Check if user needs daily reset based on last reset time."""
        user_state = await self.get_user_state(user_id)
        if not user_state:
            return True
        
        # Check if it's past midnight UTC since last reset
        now = datetime.now(timezone.utc)
        last_reset = user_state.last_daily_reset
        
        # If different day, need reset
        return now.date() > last_reset.date()
    
    async def close(self):
        """Close database connections."""
        # aiosqlite connections are closed automatically
        pass


# Global instance
db_manager = DatabaseManager()
