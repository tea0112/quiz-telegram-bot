"""Main Telegram bot implementation."""

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Poll
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F

from config import config
from database import db_manager
from google_sheets import sheets_client
from quiz_logic import quiz_manager
from scheduler import daily_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command with optional parameters."""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Create or update user in database
    await db_manager.create_or_update_user(user_id, username)
    
    # Check if there's a start parameter (from channel buttons)
    command_args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    if command_args:
        start_param = command_args[0]
        
        if start_param == "practice":
            # User clicked "Start Practice" from channel
            await cmd_practice(message)
            return
        elif start_param == "stats":
            # User clicked "View Stats" from channel
            await cmd_stats(message)
            return
    
    # Default welcome message
    welcome_text = """
🎯 **Welcome to the English Quiz Bot!**

I'm here to help you improve your English through daily practice quizzes. Here's what I can do:

📚 **Daily Practice**: Get 5 questions every day to build a consistent learning habit
💪 **Extra Practice**: Practice unlimited additional questions after completing your daily quota
🎯 **Topic Focus**: Choose specific topics to focus your practice
📊 **Track Progress**: Monitor your improvement over time

**Available Commands:**
• `/practice` - Start your daily quiz or practice more questions
• `/topics` - Browse and select specific topics to practice
• `/stats` - View your learning statistics

Ready to start learning? Use `/practice` to begin your first quiz!

Good luck! 🍀
"""
    
    await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("practice"))
async def cmd_practice(message: types.Message):
    """Handle /practice command."""
    user_id = message.from_user.id
    
    try:
        # Check if user has an active session
        active_session = quiz_manager.get_active_session(user_id)
        if active_session:
            # Continue current session
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                await send_question(message, current_question, active_session)
                return
        
        # Check if user can start daily quiz
        can_start_daily = await quiz_manager.can_start_daily_quiz(user_id)
        
        if can_start_daily:
            # Start daily quiz
            session = await quiz_manager.start_daily_quiz(user_id)
            if session:
                current_question = quiz_manager.get_current_question(user_id)
                if current_question:
                    await message.answer("🌟 **Starting your daily quiz!**\n", parse_mode="Markdown")
                    await send_question(message, current_question, session)
                else:
                    await message.answer("❌ Sorry, I couldn't prepare your quiz. Please try again later.")
            else:
                await message.answer("❌ Sorry, I couldn't start your quiz. Please try again later.")
        else:
            # Offer practice session
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Start Practice Session", callback_data="start_practice")],
                [InlineKeyboardButton(text="📚 Choose Topic", callback_data="choose_topic")]
            ])
            
            await message.answer(
                "✅ **Daily quiz completed!**\n\n"
                "Want to practice more? Choose an option below:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Error in practice command: {e}")
        await message.answer("❌ An error occurred. Please try again later.")


@dp.message(Command("topics"))
async def cmd_topics(message: types.Message):
    """Handle /topics command."""
    try:
        topics = await sheets_client.get_topics()
        
        if not topics:
            await message.answer("📚 No topics available at the moment. Please try again later.")
            return
        
        # Create keyboard with topics
        keyboard = InlineKeyboardBuilder()
        for topic in topics:
            keyboard.row(InlineKeyboardButton(
                text=f"📖 {topic}", 
                callback_data=f"topic_{topic}"
            ))
        
        keyboard.row(InlineKeyboardButton(
            text="🔀 Random Topics", 
            callback_data="topic_random"
        ))
        
        await message.answer(
            "📚 **Available Topics:**\n\n"
            "Choose a topic to start practicing:",
            reply_markup=keyboard.as_markup(),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Error in topics command: {e}")
        await message.answer("❌ An error occurred while fetching topics. Please try again later.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Handle /stats command."""
    try:
        user_id = message.from_user.id
        stats = await quiz_manager.get_user_stats(user_id)
        
        if not stats:
            await message.answer("📊 No statistics available yet. Start practicing to see your progress!")
            return
        
        stats_text = f"""
📊 **Your Learning Statistics**

**Today's Progress:**
• Daily questions: {stats['daily_completed']}/{stats['daily_limit']}
• Status: {'✅ Completed' if stats['can_practice_more'] else '⏳ In progress'}

**Overall Statistics:**
• Total questions answered: {stats['total_questions']}
• Correct answers: {stats['total_correct']}
• Accuracy: {stats['accuracy']:.1f}%

{'💪 Great job! Keep practicing to improve your score!' if stats['accuracy'] >= 70 else '📈 Keep practicing to boost your accuracy!'}
"""
        
        await message.answer(stats_text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await message.answer("❌ An error occurred while fetching your statistics.")


@dp.message(F.text & F.chat.type.in_(["group", "supergroup"]) & ~F.text.startswith("/"))
async def handle_group_messages(message: types.Message):
    """Handle non-command messages in groups and supergroups - look for bot mentions or continuing quiz sessions."""
    try:
        user_id = message.from_user.id
        text = message.text.lower() if message.text else ""
        
        # Get bot info to check for mentions
        bot_info = await bot.get_me()
        bot_username = bot_info.username.lower()
        
        # Only respond if bot is explicitly mentioned or specific keywords are used
        is_bot_mentioned = (
            f"@{bot_username}" in text or
            message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
        )
        
        # Or if user types specific quiz-related keywords
        quiz_keywords = ["quiz", "practice", "continue", "next question"]
        has_quiz_keywords = any(keyword in text for keyword in quiz_keywords)
        
        if not (is_bot_mentioned or has_quiz_keywords):
            return  # Ignore other group messages
        
        # Check if user has an active session
        active_session = quiz_manager.get_active_session(user_id)
        
        if active_session:
            # User has active session - continue quiz
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                await send_question_to_user(user_id, current_question, active_session)
                await message.reply("📱 Next question sent to your private messages!", parse_mode="Markdown")
            else:
                await message.reply("✅ Quiz completed! Use /practice to start a new one.", parse_mode="Markdown")
        else:
            # No active session - suggest starting
            await message.reply("👋 Hi! Use /practice to start a quiz.", parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Error handling group message: {e}")


@dp.channel_post()
async def handle_channel_posts(channel_post: types.Message):
    """Handle channel posts - add inline buttons for users to interact."""
    try:
        # Only handle posts that mention quiz or practice
        if not channel_post.text:
            return
            
        text = channel_post.text.lower()
        quiz_keywords = ["quiz", "practice", "learn", "english", "question"]
        
        if not any(keyword in text for keyword in quiz_keywords):
            return
        
        # Add inline keyboard for users to start practicing
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Start Practice", url=f"https://t.me/{(await bot.get_me()).username}?start=practice")],
            [InlineKeyboardButton(text="📊 View My Stats", url=f"https://t.me/{(await bot.get_me()).username}?start=stats")]
        ])
        
        # Edit the post to add buttons (only works if bot is admin)
        try:
            await bot.edit_message_reply_markup(
                chat_id=channel_post.chat.id,
                message_id=channel_post.message_id,
                reply_markup=keyboard
            )
        except Exception:
            # If can't edit, post a new message with buttons
            await bot.send_message(
                chat_id=channel_post.chat.id,
                text="🎓 Ready to practice English? Click below to start your quiz!",
                reply_markup=keyboard
            )
    
    except Exception as e:
        logger.error(f"Error handling channel post: {e}")


@dp.callback_query(F.data == "start_practice")
async def callback_start_practice(callback: types.CallbackQuery):
    """Handle practice session start."""
    try:
        user_id = callback.from_user.id
        session = await quiz_manager.start_practice_quiz(user_id)
        
        if session:
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                await callback.message.edit_text("💪 **Starting practice session!**", parse_mode="Markdown")
                await send_question(callback.message, current_question, session)
            else:
                await callback.message.edit_text("❌ Couldn't prepare practice session. Please try again.")
        else:
            await callback.message.edit_text("❌ Couldn't start practice session. Please try again later.")
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error starting practice: {e}")
        await callback.answer("❌ An error occurred.")


@dp.callback_query(F.data == "choose_topic")
async def callback_choose_topic(callback: types.CallbackQuery):
    """Handle topic selection for practice."""
    try:
        topics = await sheets_client.get_topics()
        
        if not topics:
            await callback.message.edit_text("📚 No topics available at the moment.")
            await callback.answer()
            return
        
        # Create keyboard with topics
        keyboard = InlineKeyboardBuilder()
        for topic in topics:
            keyboard.row(InlineKeyboardButton(
                text=f"📖 {topic}", 
                callback_data=f"practice_topic_{topic}"
            ))
        
        await callback.message.edit_text(
            "📚 **Choose a topic for practice:**",
            reply_markup=keyboard.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error in topic selection: {e}")
        await callback.answer("❌ An error occurred.")


@dp.callback_query(F.data.startswith("topic_"))
async def callback_topic_selection(callback: types.CallbackQuery):
    """Handle topic selection from /topics command."""
    try:
        topic = callback.data[6:]  # Remove "topic_" prefix
        user_id = callback.from_user.id
        
        if topic == "random":
            topic = None
        
        session = await quiz_manager.start_practice_quiz(user_id, topic)
        
        if session:
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                topic_text = f" ({topic})" if topic else " (Random Topics)"
                await callback.message.edit_text(f"📚 **Starting practice{topic_text}**", parse_mode="Markdown")
                await send_question(callback.message, current_question, session)
            else:
                await callback.message.edit_text("❌ Couldn't prepare quiz. Please try again.")
        else:
            await callback.message.edit_text("❌ Couldn't start quiz. Please try again later.")
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error in topic selection: {e}")
        await callback.answer("❌ An error occurred.")


@dp.callback_query(F.data.startswith("practice_topic_"))
async def callback_practice_topic(callback: types.CallbackQuery):
    """Handle topic-specific practice start."""
    try:
        topic = callback.data[15:]  # Remove "practice_topic_" prefix
        user_id = callback.from_user.id
        
        session = await quiz_manager.start_practice_quiz(user_id, topic)
        
        if session:
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                await callback.message.edit_text(f"📚 **Practicing: {topic}**", parse_mode="Markdown")
                await send_question(callback.message, current_question, session)
            else:
                await callback.message.edit_text("❌ Couldn't prepare quiz. Please try again.")
        else:
            await callback.message.edit_text("❌ Couldn't start quiz. Please try again later.")
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error starting topic practice: {e}")
        await callback.answer("❌ An error occurred.")


@dp.poll_answer()
async def poll_answer_handler(poll_answer: types.PollAnswer):
    """Handle poll answer selection."""
    try:
        user_id = poll_answer.user.id
        option_ids = poll_answer.option_ids
        
        if not option_ids:
            return
        
        # Convert option index to letter (0->A, 1->B, etc.)
        selected_option_index = option_ids[0]
        answer = chr(ord('A') + selected_option_index)
        
        is_correct, feedback_data = await quiz_manager.submit_answer(user_id, answer)
        
        # Send feedback message
        feedback_text = quiz_manager.format_feedback(feedback_data)
        
        if feedback_data.get('is_quiz_completed'):
            # Quiz completed
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Practice More", callback_data="start_practice")],
                [InlineKeyboardButton(text="📊 View Stats", callback_data="view_stats")]
            ])
            await bot.send_message(user_id, feedback_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            # Continue to next question - automatically send next question in groups
            active_session = quiz_manager.get_active_session(user_id)
            if active_session:
                current_question = quiz_manager.get_current_question(user_id)
                if current_question:
                    # Send feedback first
                    await bot.send_message(user_id, feedback_text, parse_mode="Markdown")
                    # Then automatically send next question
                    await send_question_to_user(user_id, current_question, active_session)
                    return
            
            # Fallback if no active session
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Next Question", callback_data="next_question")]
            ])
            await bot.send_message(user_id, feedback_text, parse_mode="Markdown", reply_markup=keyboard)
    
    except Exception as e:
        logger.error(f"Error processing poll answer: {e}")


@dp.callback_query(F.data.startswith("answer_"))
async def callback_answer(callback: types.CallbackQuery):
    """Handle answer selection (legacy fallback)."""
    try:
        answer = callback.data[7:]  # Remove "answer_" prefix
        user_id = callback.from_user.id
        
        is_correct, feedback_data = await quiz_manager.submit_answer(user_id, answer)
        
        # Send feedback
        feedback_text = quiz_manager.format_feedback(feedback_data)
        
        if feedback_data.get('is_quiz_completed'):
            # Quiz completed
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Practice More", callback_data="start_practice")],
                [InlineKeyboardButton(text="📊 View Stats", callback_data="view_stats")]
            ])
            await callback.message.edit_text(feedback_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            # Continue to next question
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Next Question", callback_data="next_question")]
            ])
            await callback.message.edit_text(feedback_text, parse_mode="Markdown", reply_markup=keyboard)
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        await callback.answer("❌ An error occurred.")


@dp.callback_query(F.data == "next_question")
async def callback_next_question(callback: types.CallbackQuery):
    """Handle next question request."""
    try:
        user_id = callback.from_user.id
        session = quiz_manager.get_active_session(user_id)
        
        if session:
            current_question = quiz_manager.get_current_question(user_id)
            if current_question:
                # Delete the feedback message and send new question
                await callback.message.delete()
                await send_question(callback.message, current_question, session, edit=False)
            else:
                await callback.message.edit_text("❌ No more questions available.")
        else:
            await callback.message.edit_text("❌ No active quiz session found.")
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error getting next question: {e}")
        await callback.answer("❌ An error occurred.")


@dp.callback_query(F.data == "view_stats")
async def callback_view_stats(callback: types.CallbackQuery):
    """Handle stats viewing."""
    try:
        user_id = callback.from_user.id
        stats = await quiz_manager.get_user_stats(user_id)
        
        if stats:
            stats_text = f"""
📊 **Your Learning Statistics**

**Today's Progress:**
• Daily questions: {stats['daily_completed']}/{stats['daily_limit']}

**Overall Statistics:**
• Total questions answered: {stats['total_questions']}
• Correct answers: {stats['total_correct']}
• Accuracy: {stats['accuracy']:.1f}%
"""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Practice More", callback_data="start_practice")]
            ])
            await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await callback.message.edit_text("📊 No statistics available yet.")
        
        await callback.answer()
    
    except Exception as e:
        logger.error(f"Error viewing stats: {e}")
        await callback.answer("❌ An error occurred.")


async def send_question_to_user(user_id: int, question_data: dict, session):
    """Send a question directly to a user (works in DMs and groups)."""
    # Format question header
    question_header = f"❓ **Question {session.current_question_index + 1}/{len(session.questions)}**\n📚 **Topic:** {question_data['topic']}"
    
    # Prepare poll options
    options = []
    option_letters = ['A', 'B', 'C', 'D']
    correct_option_id = None
    
    for i, letter in enumerate(option_letters):
        option_text = question_data.get(f'option_{letter.lower()}', '')
        if option_text:
            options.append(option_text)
            # Check if this is the correct answer
            if question_data['correct_answer'].upper() == letter:
                correct_option_id = i
    
    if not options or correct_option_id is None:
        # Fallback to text message
        await bot.send_message(user_id, "❌ Error with question format. Use /practice to try again.")
        return
    
    # Send header message first
    await bot.send_message(user_id, question_header, parse_mode="Markdown")
    
    # Send poll
    try:
        poll_message = await bot.send_poll(
            chat_id=user_id,
            question=question_data['question'],
            options=options,
            type="quiz",  # This creates a quiz poll with radio buttons
            correct_option_id=correct_option_id,
            is_anonymous=False,
            allows_multiple_answers=False,
            explanation=question_data.get('explanation', '') if question_data.get('explanation') else None
        )
        
    except Exception as e:
        logger.error(f"Failed to send poll to user {user_id}: {e}")
        # Fallback message
        await bot.send_message(user_id, "❌ Error sending question. Use /practice to try again.")


async def send_question(message: types.Message, question_data: dict, session, edit: bool = False):
    """Send a question using Telegram poll with radio buttons."""
    # For group chats, send to user directly to avoid spam
    # Note: Channels are handled separately by channel_post handler
    if message.chat.type in ['group', 'supergroup']:
        await send_question_to_user(message.from_user.id, question_data, session)
        await message.reply("📱 Question sent to your private messages!", parse_mode="Markdown")
        return
    
    # Format question header
    question_header = f"❓ **Question {session.current_question_index + 1}/{len(session.questions)}**\n📚 **Topic:** {question_data['topic']}"
    
    # Prepare poll options
    options = []
    option_letters = ['A', 'B', 'C', 'D']
    correct_option_id = None
    
    for i, letter in enumerate(option_letters):
        option_text = question_data.get(f'option_{letter.lower()}', '')
        if option_text:
            options.append(option_text)
            # Check if this is the correct answer
            if question_data['correct_answer'].upper() == letter:
                correct_option_id = i
    
    if not options or correct_option_id is None:
        # Fallback to inline buttons if poll can't be created
        await send_question_fallback(message, question_data, session, edit)
        return
    
    # Send header message first
    if not edit:
        await message.answer(question_header, parse_mode="Markdown")
    
    # Send poll
    try:
        poll_message = await bot.send_poll(
            chat_id=message.chat.id,
            question=question_data['question'],
            options=options,
            type="quiz",  # This creates a quiz poll with radio buttons
            correct_option_id=correct_option_id,
            is_anonymous=False,
            allows_multiple_answers=False,
            explanation=question_data.get('explanation', '') if question_data.get('explanation') else None
        )
        
        # Store poll message for potential cleanup later
        # You could store this in the session if needed
        
    except Exception as e:
        logger.error(f"Failed to send poll: {e}")
        # Fallback to inline buttons
        await send_question_fallback(message, question_data, session, edit)


async def send_question_fallback(message: types.Message, question_data: dict, session, edit: bool = False):
    """Fallback method using inline buttons if polls fail."""
    question_text = quiz_manager.format_question(
        question_data, 
        session.current_question_index + 1, 
        len(session.questions)
    )
    
    # Create answer buttons
    keyboard = InlineKeyboardBuilder()
    options = ['A', 'B', 'C', 'D']
    
    for option in options:
        option_text = question_data.get(f'option_{option.lower()}', '')
        if option_text:
            keyboard.row(InlineKeyboardButton(
                text=f"{option}. {option_text[:30]}{'...' if len(option_text) > 30 else ''}", 
                callback_data=f"answer_{option}"
            ))
    
    if edit:
        await message.edit_text(question_text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
    else:
        await message.answer(question_text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")


async def main():
    """Main function to run the bot."""
    # Validate configuration
    if not config.validate():
        logger.error("Invalid configuration. Please check your environment variables.")
        return
    
    # Initialize database
    if not await db_manager.initialize():
        logger.error("Failed to initialize database")
        return
    
    # Initialize Google Sheets client
    if not await sheets_client.initialize():
        logger.error("Failed to initialize Google Sheets client")
        return
    
    # Start daily scheduler
    await daily_scheduler.start()
    
    logger.info("Bot is starting...")
    
    try:
        # Start polling
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        # Cleanup
        await daily_scheduler.stop()
        await db_manager.close()
        sheets_client.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
