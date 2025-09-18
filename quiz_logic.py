"""Quiz logic and session management."""

import json
import random
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from database import QuizSession, db_manager
from google_sheets import sheets_client
from config import config

import logging

logger = logging.getLogger(__name__)


class QuizManager:
    """Manages quiz sessions and logic."""
    
    def __init__(self):
        self.active_sessions: Dict[int, QuizSession] = {}  # user_id -> session
    
    async def can_start_daily_quiz(self, user_id: int) -> bool:
        """Check if user can start their daily quiz."""
        # Check if daily reset is needed
        if await db_manager.needs_daily_reset(user_id):
            await db_manager.reset_daily_progress(user_id)
        
        user_state = await db_manager.get_user_state(user_id)
        if not user_state:
            return True  # New user can start
        
        return user_state.daily_questions_completed < config.DAILY_QUESTION_LIMIT
    
    async def start_daily_quiz(self, user_id: int) -> Optional[QuizSession]:
        """Start a daily quiz session for the user."""
        if not await self.can_start_daily_quiz(user_id):
            return None
        
        questions = await self._get_random_questions(config.DAILY_QUESTION_LIMIT)
        if not questions:
            logger.error("No questions available for daily quiz")
            return None
        
        session = QuizSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            session_type='daily',
            topic=None,
            questions=questions,
            current_question_index=0,
            correct_answers=0,
            answers_given=[],
            started_at=datetime.now(timezone.utc),
            is_completed=False
        )
        
        self.active_sessions[user_id] = session
        return session
    
    async def start_practice_quiz(self, user_id: int, topic: Optional[str] = None) -> Optional[QuizSession]:
        """Start a practice quiz session for the user."""
        if topic:
            questions = await sheets_client.get_questions_by_topic(topic)
            if len(questions) < config.DAILY_QUESTION_LIMIT:
                # If not enough questions in topic, supplement with random questions
                additional_needed = config.DAILY_QUESTION_LIMIT - len(questions)
                random_questions = await self._get_random_questions(additional_needed, exclude_topics=[topic])
                questions.extend(random_questions)
        else:
            questions = await self._get_random_questions(config.DAILY_QUESTION_LIMIT)
        
        if not questions:
            logger.error("No questions available for practice quiz")
            return None
        
        # Shuffle and limit to exact number needed
        random.shuffle(questions)
        questions = questions[:config.DAILY_QUESTION_LIMIT]
        
        session = QuizSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            session_type='practice',
            topic=topic,
            questions=questions,
            current_question_index=0,
            correct_answers=0,
            answers_given=[],
            started_at=datetime.now(timezone.utc),
            is_completed=False
        )
        
        self.active_sessions[user_id] = session
        return session
    
    async def _get_random_questions(self, count: int, exclude_topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get random questions from the sheets."""
        all_questions = await sheets_client.fetch_questions()
        
        if exclude_topics:
            all_questions = [q for q in all_questions if q['topic'] not in exclude_topics]
        
        if len(all_questions) < count:
            logger.warning(f"Only {len(all_questions)} questions available, requested {count}")
            return all_questions
        
        return random.sample(all_questions, count)
    
    def get_active_session(self, user_id: int) -> Optional[QuizSession]:
        """Get the active session for a user."""
        return self.active_sessions.get(user_id)
    
    def get_current_question(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get the current question for a user's active session."""
        session = self.get_active_session(user_id)
        if not session or session.is_completed:
            return None
        
        if session.current_question_index >= len(session.questions):
            return None
        
        return session.questions[session.current_question_index]
    
    async def submit_answer(self, user_id: int, answer: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Submit an answer for the current question.
        
        Returns:
            Tuple of (is_correct, feedback_data)
            feedback_data contains: correct_answer, explanation, is_last_question
        """
        session = self.get_active_session(user_id)
        if not session or session.is_completed:
            return False, {}
        
        current_question = self.get_current_question(user_id)
        if not current_question:
            return False, {}
        
        # Check if answer is correct
        correct_answer = current_question['correct_answer'].strip().upper()
        user_answer = answer.strip().upper()
        is_correct = user_answer == correct_answer
        
        # Update session
        session.answers_given.append(answer)
        if is_correct:
            session.correct_answers += 1
        
        # Prepare feedback data
        feedback_data = {
            'is_correct': is_correct,
            'correct_answer': current_question['correct_answer'],
            'explanation': current_question.get('explanation', ''),
            'question_number': session.current_question_index + 1,
            'total_questions': len(session.questions)
        }
        
        # Move to next question
        session.current_question_index += 1
        
        # Check if quiz is completed
        if session.current_question_index >= len(session.questions):
            await self._complete_session(session)
            feedback_data['is_quiz_completed'] = True
            feedback_data['final_score'] = session.correct_answers
            feedback_data['session_type'] = session.session_type
        else:
            feedback_data['is_quiz_completed'] = False
        
        return is_correct, feedback_data
    
    async def _complete_session(self, session: QuizSession):
        """Complete a quiz session and update user stats."""
        session.is_completed = True
        
        # Update database
        await db_manager.save_quiz_session(session)
        await db_manager.update_user_stats(
            session.user_id, 
            len(session.questions), 
            session.correct_answers
        )
        
        # Update daily progress if it's a daily quiz
        if session.session_type == 'daily':
            user_state = await db_manager.get_user_state(session.user_id)
            if user_state:
                new_daily_count = user_state.daily_questions_completed + len(session.questions)
                await db_manager.update_daily_progress(session.user_id, new_daily_count)
        
        # Remove from active sessions
        if session.user_id in self.active_sessions:
            del self.active_sessions[session.user_id]
    
    def format_question(self, question_data: Dict[str, Any], question_number: int, total_questions: int) -> str:
        """Format a question for display."""
        text = f"❓ **Question {question_number}/{total_questions}**\n\n"
        text += f"📚 **Topic:** {question_data['topic']}\n\n"
        text += f"{question_data['question']}\n\n"
        
        options = ['A', 'B', 'C', 'D']
        for i, option in enumerate(options):
            option_text = question_data.get(f'option_{option.lower()}', '')
            if option_text:
                text += f"{option}. {option_text}\n"
        
        return text
    
    def format_feedback(self, feedback_data: Dict[str, Any]) -> str:
        """Format feedback message after an answer."""
        if feedback_data['is_correct']:
            text = "✅ **Correct!**\n\n"
        else:
            text = "❌ **Incorrect**\n\n"
            text += f"The correct answer is: **{feedback_data['correct_answer']}**\n\n"
        
        if feedback_data.get('explanation'):
            text += f"💡 **Explanation:** {feedback_data['explanation']}\n\n"
        
        if feedback_data.get('is_quiz_completed'):
            text += f"🎉 **Quiz Completed!**\n"
            text += f"📊 **Final Score:** {feedback_data['final_score']}/{feedback_data['question_number']}\n"
            
            accuracy = (feedback_data['final_score'] / feedback_data['question_number']) * 100
            text += f"🎯 **Accuracy:** {accuracy:.1f}%\n\n"
            
            if feedback_data['session_type'] == 'daily':
                text += "🌟 Daily quiz completed! Come back tomorrow for more practice.\n"
                text += "💪 Want to practice more? Use /practice for additional questions!"
            else:
                text += "💪 Great practice session! Use /practice to start another round!"
        
        return text
    
    async def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user statistics."""
        user_state = await db_manager.get_user_state(user_id)
        if not user_state:
            return None
        
        # Check if daily reset is needed
        if await db_manager.needs_daily_reset(user_id):
            await db_manager.reset_daily_progress(user_id)
            user_state = await db_manager.get_user_state(user_id)  # Refresh
        
        accuracy = 0
        if user_state.total_questions_answered > 0:
            accuracy = (user_state.total_correct_answers / user_state.total_questions_answered) * 100
        
        return {
            'daily_completed': user_state.daily_questions_completed,
            'daily_limit': config.DAILY_QUESTION_LIMIT,
            'can_practice_more': user_state.daily_questions_completed >= config.DAILY_QUESTION_LIMIT,
            'total_questions': user_state.total_questions_answered,
            'total_correct': user_state.total_correct_answers,
            'accuracy': accuracy
        }


# Global instance
quiz_manager = QuizManager()
