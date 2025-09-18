#!/bin/bash

# Quiz Telegram Bot startup script

echo "🤖 Starting Quiz Telegram Bot..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Please copy env.example to .env and configure it."
    echo "At minimum, you need to set TELEGRAM_BOT_TOKEN"
    exit 1
fi

# Check if questions directory exists and has CSV files
if [ ! -d questions ]; then
    echo "❌ 'questions/' directory not found."
    echo "Please create topic-based CSV files in the questions/ directory."
    exit 1
fi

csv_count=$(find questions -name "*.csv" | wc -l)
if [ "$csv_count" -eq 0 ]; then
    echo "❌ questions/ directory exists but contains no CSV files."
    echo "Please add topic-based CSV files (e.g., grammar.csv, vocabulary.csv) to the questions/ directory."
    exit 1
fi

echo "📚 Found $csv_count topic CSV files in questions/ directory."

# Install dependencies if needed
echo "📦 Checking dependencies..."
uv sync

# Run the bot
echo "🚀 Starting the bot..."
uv run bot.py
