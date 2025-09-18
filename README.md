# Quiz Telegram Bot

A Telegram bot designed to help users learn and practice English through daily quizzes. Sources questions from Google Sheets with automatic CSV fallback for reliability.

## Features

- **Daily Practice**: 5 questions per day to build consistent learning habits
- **Extra Practice**: Unlimited additional practice sessions after completing daily quota
- **Topic-based Learning**: Choose specific topics to focus your practice
- **Progress Tracking**: Monitor your learning statistics and accuracy
- **Flexible Data Sources**: Google Sheets integration with topic-based CSV fallback
- **uv Package Management**: Modern Python package management with uv

## Setup Instructions

### 1. Prerequisites

- Python 3.8.1 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- A Telegram Bot Token (from @BotFather on Telegram)
- Google Cloud Project with Sheets API enabled (optional)
- Google Service Account credentials (optional)

### 2. Installation

1. **Install uv** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Clone or download this repository**

3. **Install dependencies with uv**:
```bash
uv sync
```

This will create a virtual environment and install all dependencies automatically.

### 3. Configuration

1. **Telegram Bot Setup:**
   - Message @BotFather on Telegram
   - Create a new bot with `/newbot`
   - Save the bot token

2. **Google Sheets Setup:**
   - Create a Google Cloud Project
   - Enable the Google Sheets API
   - Create a Service Account and download the JSON credentials file
   - Create a Google Sheet with the following columns:
     - A: Topic
     - B: Question
     - C: Option A
     - D: Option B
     - E: Option C
     - F: Option D
     - G: Correct Answer (A, B, C, or D)
     - H: Explanation
   - Share your Google Sheet with the service account email (found in credentials.json)

3. **Environment Configuration:**
   - Copy `env.example` to `.env`
   - **Required configuration:**
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```
   - **Optional Google Sheets configuration** (if not provided, will use CSV fallback):
```bash
GOOGLE_SHEETS_ID=your_google_sheets_id_here
GOOGLE_CREDENTIALS_FILE=path/to/your/credentials.json
```
   - **Other optional settings:**
```bash
DATABASE_PATH=quiz_bot.db
DAILY_QUESTION_LIMIT=5
TIMEZONE=UTC
```

**Note:** If Google Sheets configuration is missing or fails, the bot will automatically use topic-based CSV files from the `questions/` directory.

### 4. Data Source Formats

#### 4.1. Google Sheets Format

Your Google Sheet should have this structure:

| Topic | Question | Option A | Option B | Option C | Option D | Correct Answer | Explanation |
|-------|----------|----------|----------|----------|----------|----------------|-------------|
| Grammar | What is the past tense of "go"? | went | goes | going | gone | A | "Went" is the simple past tense of "go" |
| Vocabulary | What does "ubiquitous" mean? | rare | common | expensive | beautiful | B | Ubiquitous means present everywhere |

#### 4.2. Topic-Based CSV Files (Required for CSV fallback)

Create separate CSV files for each topic in the `questions/` directory:

**questions/grammar.csv:**
```csv
Question,Option A,Option B,Option C,Option D,Correct Answer,Explanation
What is the past tense of "go"?,went,goes,going,gone,A,"Went" is the simple past tense of "go"
Which sentence is correct?,I has a car,I have a car,I having a car,I haved a car,B,"Have" is the correct present tense form for "I"
```

**questions/vocabulary.csv:**
```csv
Question,Option A,Option B,Option C,Option D,Correct Answer,Explanation
What does "ubiquitous" mean?,rare,common everywhere,expensive,beautiful,B,Ubiquitous means present or found everywhere
What is a synonym for "happy"?,sad,angry,joyful,tired,C,Joyful means feeling or expressing great happiness
```

**Benefits of topic-based CSV files:**
- ✅ **Easy Management**: Each topic in its own file
- ✅ **Clean Organization**: No Topic column needed
- ✅ **Version Control Friendly**: Changes to one topic don't affect others
- ✅ **Team Collaboration**: Different people can work on different topics


### 5. Running the Bot

**With uv (recommended):**
```bash
uv run bot.py
```

**Or activate the virtual environment first:**
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python bot.py
```

### 6. Environment Variables Reference

These can be set in `.env` or passed at runtime:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token from BotFather |
| `GOOGLE_SHEETS_ID` | No | - | Spreadsheet ID for Google Sheets datasource |
| `GOOGLE_CREDENTIALS_FILE` | No | `credentials.json` | Path to service account JSON |
| `QUESTIONS_DIRECTORY` | No | `questions` | Directory of topic-based CSV files |
| `DATABASE_PATH` | No | `quiz_bot.db` (local) / `/app/data/quiz_bot.db` (Docker) | SQLite DB path |
| `DAILY_QUESTION_LIMIT` | No | `5` | Number of questions per session |
| `TIMEZONE` | No | `UTC` | Bot timezone label |

### 7. Run with Docker (Production-ready)

Build the image:
```bash
docker build -t quiz-telegram-bot:latest .
```

Run with volumes for data and questions:
```bash
docker run -d \
  --name quiz-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e QUESTIONS_DIRECTORY=/app/questions \
  -e DATABASE_PATH=/app/data/quiz_bot.db \
  -v $(pwd)/questions:/app/questions:ro \
  -v $(pwd)/data:/app/data \
  quiz-telegram-bot:latest
```

### 8. Run with docker-compose

```bash
docker compose up -d --build
```

This will:
- Mount `./questions` (read-only) into the container
- Persist the SQLite database in `./data`
- Read configuration from `.env` when available

### 9. Makefile Shortcuts

For local development and Docker workflows:

```bash
# First-time setup
make env        # create .env from template
make sync       # install deps via uv

# Run locally
make run

# Code quality
make fmt        # isort + black
make lint       # flake8
make test       # pytest

# Docker
make docker-build
make docker-run
make docker-logs

# Compose
make compose-up
make compose-logs
```

## Bot Commands

The bot works in:
- **Private messages** (direct chats with the bot)
- **Groups and Supergroups** (questions sent to private messages to avoid spam)
- **Channels** (adds interactive buttons to channel posts)

Commands available:
- `/start` - Welcome message and bot introduction
- `/practice` - Start daily quiz or practice more questions
- `/topics` - Browse and select specific topics
- `/stats` - View your learning statistics

**Channel Behavior**: 
- When admins post about "quiz", "practice", or "English" in channels, the bot automatically adds interactive buttons
- Users click these buttons to start their quiz in private messages with the bot
- This works even when the channel has chat disabled for regular users

**Group Behavior**: 
- Questions are sent to private messages to keep group chat clean
- Users can type "quiz", "practice", or mention the bot to continue active sessions

## File Structure

```
quiz-telegram-bot/
├── bot.py                  # Main bot implementation
├── config.py               # Configuration management
├── database.py             # User state and data management
├── google_sheets.py        # Google Sheets integration with CSV fallback
├── quiz_logic.py           # Quiz session management
├── scheduler.py            # Daily reset scheduler
├── pyproject.toml          # uv project configuration and dependencies
├── Dockerfile              # Production container image
├── docker-compose.yaml     # Local dev/ops with volumes
├── Makefile                # Developer shortcuts
├── questions/              # Topic-based CSV files (recommended)
│   ├── grammar.csv         # Grammar questions
│   ├── vocabulary.csv      # Vocabulary questions
│   ├── idioms.csv          # Idioms questions
│   └── reading.csv         # Reading comprehension questions
├── env.example             # Environment variables template
└── README.md              # This file
```

## Features Implementation

### Daily Quiz System
- Users get 5 questions per day
- Progress resets at midnight UTC
- Tracks completion status per user

### Practice Sessions
- Unlimited practice after daily quota
- Topic-specific practice available
- Random question selection

### User Interface
- Telegram Polls (Quiz Mode) with radio buttons
- Automatic correct answer reveal and explanations
- Progress tracking and statistics

### Data Management
- SQLite database for user states
- Google Sheets for question content with topic-based CSV fallback
- Automatic daily reset functionality
- Reliable operation even without Google Sheets access
- Organized topic-specific question files for easy management

## Troubleshooting

### Common Issues

1. **Bot doesn't respond:**
   - Check if the bot token is correct
   - Ensure the bot is started with `/start`

2. **Google Sheets errors:**
   - Verify the service account has access to the sheet
   - Check if the sheet ID is correct
   - Ensure the credentials file path is valid
   - **Note:** The bot will automatically fallback to CSV if Google Sheets fails

3. **Database errors:**
   - Check write permissions in the directory
   - Ensure SQLite is properly installed

### Logs

The bot logs important events and errors. Check the console output for debugging information.

## Requirements Met

This implementation fulfills all requirements from the Product Requirements Document:

✅ **Functional Requirements:**
- FR-1: Google Sheets content sourcing
- FR-2: Daily quiz (5 questions) with tracking
- FR-3: Additional practice sessions
- FR-4: Daily reset at midnight UTC
- FR-5: `/start` command with welcome message
- FR-6: `/practice` command with session management
- FR-7: `/topics` command with topic selection
- FR-8: Interactive buttons and immediate feedback

✅ **Non-functional Requirements:**
- NFR-1: Python with aiogram library
- NFR-2: Google Sheets + SQLite for data storage
- NFR-3: Optimized for quick response times
- NFR-5: Comprehensive error handling
- NFR-6: Secure environment variable management

## Support

For issues or questions, please check the logs and verify your configuration settings. The bot includes comprehensive error handling and logging to help with troubleshooting.
