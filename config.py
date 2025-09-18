"""Configuration management for the Quiz Telegram Bot."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for the bot."""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    # Google Sheets Configuration
    GOOGLE_SHEETS_ID: str = os.getenv('GOOGLE_SHEETS_ID', '')
    GOOGLE_CREDENTIALS_FILE: str = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    
    # Database Configuration
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'quiz_bot.db')
    
    # Questions Configuration
    QUESTIONS_DIRECTORY: str = os.getenv('QUESTIONS_DIRECTORY', 'questions')
    DATA_SOURCE: str = os.getenv('DATA_SOURCE', 'auto')  # 'auto', 'csv', 'sheets'
    
    # Bot Configuration
    DAILY_QUESTION_LIMIT: int = int(os.getenv('DAILY_QUESTION_LIMIT', '5'))
    TIMEZONE: str = os.getenv('TIMEZONE', 'UTC')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configuration values are present."""
        # Only Telegram bot token is required, Google Sheets is optional
        required_fields = [
            ('TELEGRAM_BOT_TOKEN', cls.TELEGRAM_BOT_TOKEN),
        ]
        
        missing_fields = []
        for field_name, field_value in required_fields:
            if not field_value:
                missing_fields.append(field_name)
        
        if missing_fields:
            print(f"Missing required configuration: {', '.join(missing_fields)}")
            return False
        
        # Check if Google Sheets is configured
        if not cls.GOOGLE_SHEETS_ID or not cls.GOOGLE_CREDENTIALS_FILE:
            print("Google Sheets configuration not complete, will use CSV fallback")
        
        return True


# Create a global config instance
config = Config()
