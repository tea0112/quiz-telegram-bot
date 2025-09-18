"""Google Sheets integration for the Quiz Telegram Bot with CSV fallback."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import os
import csv
import pandas as pd

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from config import config

logger = logging.getLogger(__name__)

if not GOOGLE_AVAILABLE:
    logger.warning("Google API libraries not available, will use CSV fallback only")


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API with CSV fallback."""
    
    def __init__(self):
        self.service = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._questions_cache = None
        self._topics_cache = None
        self.use_fallback = False
        self.questions_directory = config.QUESTIONS_DIRECTORY
    
    async def initialize(self) -> bool:
        """Initialize the Google Sheets service with CSV fallback."""
        # Check if questions directory exists
        if not os.path.exists(self.questions_directory):
            logger.error(f"Questions directory not found: {self.questions_directory}")
            return False
        
        # Check DATA_SOURCE environment variable
        data_source = config.DATA_SOURCE.lower()
        
        if data_source == 'csv':
            logger.info("DATA_SOURCE=csv: Using CSV files only")
            self.use_fallback = True
            return True
        elif data_source == 'sheets':
            logger.info("DATA_SOURCE=sheets: Using Google Sheets only")
            if not GOOGLE_AVAILABLE:
                logger.error("Google API libraries not available but DATA_SOURCE=sheets")
                return False
            if not config.GOOGLE_SHEETS_ID or not config.GOOGLE_CREDENTIALS_FILE:
                logger.error("Google Sheets not configured but DATA_SOURCE=sheets")
                return False
        else:
            # data_source == 'auto' (default)
            logger.info("DATA_SOURCE=auto: Trying Google Sheets with CSV fallback")
        
        # Try to initialize Google Sheets if available and not forced CSV
        if data_source != 'csv' and GOOGLE_AVAILABLE and config.GOOGLE_SHEETS_ID and config.GOOGLE_CREDENTIALS_FILE:
            try:
                # Check if credentials file exists
                if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
                    if data_source == 'sheets':
                        logger.error(f"Google credentials file not found: {config.GOOGLE_CREDENTIALS_FILE}")
                        return False
                    logger.warning(f"Google credentials file not found: {config.GOOGLE_CREDENTIALS_FILE}")
                    logger.info("Falling back to CSV file")
                    self.use_fallback = True
                    return True
                
                # Load credentials and build service
                loop = asyncio.get_event_loop()
                self.service = await loop.run_in_executor(
                    self.executor, self._build_service
                )
                
                # Test the connection by fetching a small range
                await self._test_connection()
                logger.info("Google Sheets client initialized successfully")
                return True
                
            except Exception as e:
                if data_source == 'sheets':
                    logger.error(f"Failed to initialize Google Sheets client: {e}")
                    return False
                logger.warning(f"Failed to initialize Google Sheets client: {e}")
                logger.info("Falling back to CSV file")
                self.use_fallback = True
                return True
        else:
            if data_source == 'sheets':
                logger.error("Google Sheets not configured but DATA_SOURCE=sheets")
                return False
            logger.info("Google Sheets not configured or available, using CSV fallback")
            self.use_fallback = True
            return True
    
    def _build_service(self):
        """Build the Google Sheets service (runs in thread)."""
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        credentials = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=scopes
        )
        return build('sheets', 'v4', credentials=credentials)
    
    async def _test_connection(self):
        """Test the connection to Google Sheets."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self.service.spreadsheets().get(
                spreadsheetId=config.GOOGLE_SHEETS_ID
            ).execute()
        )
    
    async def fetch_questions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all questions from Google Sheet or CSV fallback.
        
        Args:
            force_refresh: If True, ignore cache and fetch fresh data
            
        Returns:
            List of question dictionaries with keys:
            - topic, question, option_a, option_b, option_c, option_d, 
              correct_answer, explanation
        """
        if self._questions_cache and not force_refresh:
            return self._questions_cache
        
        try:
            if self.use_fallback:
                # Use CSV fallback
                loop = asyncio.get_event_loop()
                questions = await loop.run_in_executor(
                    self.executor, self._fetch_questions_from_csv
                )
                logger.info(f"Loaded {len(questions)} questions from CSV fallback")
            else:
                # Try Google Sheets first
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        self.executor, self._fetch_questions_sync
                    )
                    questions = self._parse_questions(result)
                    logger.info(f"Fetched {len(questions)} questions from Google Sheets")
                except Exception as e:
                    logger.warning(f"Google Sheets failed: {e}, falling back to CSV")
                    self.use_fallback = True
                    questions = await loop.run_in_executor(
                        self.executor, self._fetch_questions_from_csv
                    )
                    logger.info(f"Loaded {len(questions)} questions from CSV fallback")
            
            self._questions_cache = questions
            self._topics_cache = None  # Clear topics cache to refresh
            return questions
            
        except Exception as e:
            logger.error(f"Failed to fetch questions from both sources: {e}")
            return []
    
    def _fetch_questions_sync(self):
        """Synchronous method to fetch data from Google Sheets."""
        # Assuming the sheet has headers in row 1 and data starts from row 2
        range_name = 'A:H'  # Topic, Question, Option A, B, C, D, Correct Answer, Explanation
        
        result = self.service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range=range_name
        ).execute()
        
        return result.get('values', [])
    
    def _parse_questions(self, raw_data: List[List[str]]) -> List[Dict[str, Any]]:
        """Parse raw Google Sheets data into question dictionaries."""
        if not raw_data:
            return []
        
        # Skip header row
        questions = []
        headers = ['topic', 'question', 'option_a', 'option_b', 'option_c', 
                  'option_d', 'correct_answer', 'explanation']
        
        for i, row in enumerate(raw_data[1:], start=2):  # Start from row 2
            if len(row) < 7:  # Minimum required columns
                logger.warning(f"Skipping row {i}: insufficient data")
                continue
            
            # Pad row to ensure all columns exist
            while len(row) < 8:
                row.append('')
            
            question_dict = {}
            for j, header in enumerate(headers):
                question_dict[header] = row[j].strip() if j < len(row) else ''
            
            # Validate required fields
            if not all([question_dict['topic'], question_dict['question'], 
                       question_dict['correct_answer']]):
                logger.warning(f"Skipping row {i}: missing required fields")
                continue
            
            questions.append(question_dict)
        
        return questions
    
    def _fetch_questions_from_csv(self) -> List[Dict[str, Any]]:
        """Load questions from topic-specific CSV files."""
        questions = []
        
        # Load from topic-specific CSV files
        if os.path.exists(self.questions_directory):
            questions = self._load_from_topic_csvs()
            if questions:
                logger.info(f"Loaded {len(questions)} questions from topic CSV files")
                return questions
        
        logger.error(f"No CSV files found in {self.questions_directory}")
        return []
    
    def _load_from_topic_csvs(self) -> List[Dict[str, Any]]:
        """Load questions from topic-specific CSV files in the questions directory."""
        all_questions = []
        
        try:
            # Get all CSV files in the questions directory
            csv_files = [f for f in os.listdir(self.questions_directory) if f.endswith('.csv')]
            
            if not csv_files:
                logger.warning(f"No CSV files found in {self.questions_directory}")
                return []
            
            for csv_file in csv_files:
                topic_name = os.path.splitext(csv_file)[0].title()  # filename becomes topic
                file_path = os.path.join(self.questions_directory, csv_file)
                
                try:
                    questions = self._load_topic_csv_file(file_path, topic_name)
                    all_questions.extend(questions)
                    logger.debug(f"Loaded {len(questions)} questions from {csv_file}")
                except Exception as e:
                    logger.warning(f"Failed to load {csv_file}: {e}")
                    continue
            
            return all_questions
            
        except Exception as e:
            logger.error(f"Error loading from topic CSV files: {e}")
            return []
    
    def _load_topic_csv_file(self, file_path: str, topic_name: str) -> List[Dict[str, Any]]:
        """Load questions from a single topic CSV file."""
        questions = []
        
        try:
            # Try pandas first
            df = pd.read_csv(file_path)
            
            # Expected columns for topic files (no Topic column needed)
            expected_columns = ['question', 'option_a', 'option_b', 'option_c', 
                              'option_d', 'correct_answer', 'explanation']
            
            # Convert column names to lowercase with underscores
            df.columns = df.columns.str.lower().str.replace(' ', '_')
            
            # Check required columns
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"Missing columns in {file_path}: {missing_columns}")
                return []
            
            # Convert to question dictionaries
            for index, row in df.iterrows():
                question_dict = {
                    'topic': topic_name,  # Use filename as topic
                    'question': str(row['question']).strip() if pd.notna(row['question']) else '',
                    'option_a': str(row['option_a']).strip() if pd.notna(row['option_a']) else '',
                    'option_b': str(row['option_b']).strip() if pd.notna(row['option_b']) else '',
                    'option_c': str(row['option_c']).strip() if pd.notna(row['option_c']) else '',
                    'option_d': str(row['option_d']).strip() if pd.notna(row['option_d']) else '',
                    'correct_answer': str(row['correct_answer']).strip() if pd.notna(row['correct_answer']) else '',
                    'explanation': str(row['explanation']).strip() if pd.notna(row['explanation']) else ''
                }
                
                # Validate required fields
                if not all([question_dict['question'], question_dict['correct_answer']]):
                    logger.warning(f"Skipping row {index + 2} in {file_path}: missing required fields")
                    continue
                
                questions.append(question_dict)
            
            return questions
            
        except Exception as e:
            logger.warning(f"Failed to read {file_path} with pandas: {e}, trying basic CSV reader")
            
            # Fallback to basic CSV reader
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    
                    for row_num, row in enumerate(reader, start=2):
                        # Normalize keys
                        normalized_row = {}
                        for key, value in row.items():
                            normalized_key = key.lower().replace(' ', '_')
                            normalized_row[normalized_key] = value.strip() if value else ''
                        
                        question_dict = {
                            'topic': topic_name,
                            'question': normalized_row.get('question', ''),
                            'option_a': normalized_row.get('option_a', ''),
                            'option_b': normalized_row.get('option_b', ''),
                            'option_c': normalized_row.get('option_c', ''),
                            'option_d': normalized_row.get('option_d', ''),
                            'correct_answer': normalized_row.get('correct_answer', ''),
                            'explanation': normalized_row.get('explanation', '')
                        }
                        
                        # Validate required fields
                        if not all([question_dict['question'], question_dict['correct_answer']]):
                            logger.warning(f"Skipping row {row_num} in {file_path}: missing required fields")
                            continue
                        
                        questions.append(question_dict)
                
                return questions
                
            except Exception as csv_error:
                logger.error(f"Failed to read {file_path}: {csv_error}")
                return []
    
    
    async def get_topics(self) -> List[str]:
        """Get all unique topics from the questions."""
        if self._topics_cache:
            return self._topics_cache
        
        questions = await self.fetch_questions()
        topics = list(set(q['topic'] for q in questions if q['topic']))
        topics.sort()
        
        self._topics_cache = topics
        return topics
    
    async def get_questions_by_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Get all questions for a specific topic."""
        questions = await self.fetch_questions()
        return [q for q in questions if q['topic'].lower() == topic.lower()]
    
    def close(self):
        """Clean up resources."""
        if self.executor:
            self.executor.shutdown(wait=True)


# Global instance
sheets_client = GoogleSheetsClient()
