# Product Requirements Document: Quiz Telegram Bot

### **Version 1.2**

---

## 1. Introduction & Vision

### **1.1. Introduction**

This document outlines the requirements for the **Quiz Telegram Bot**, a tool designed to help users learn and practice English in a convenient and engaging way. The bot will deliver daily quizzes directly through the Telegram messaging app, using questions sourced from a Google Sheet with automatic CSV fallback for reliability.

### **1.2. Vision**

The vision is to create a simple, accessible, and effective learning tool that encourages consistent daily practice. By integrating with a popular messaging platform, the bot removes the friction of downloading a separate app, making it easier for users to build a lasting language-learning habit.

---

## 2. User Stories

### **2.1. User Persona**

The primary user is an **English learner** of any level who wants to improve their skills through regular, bite-sized practice sessions.

### **2.2. Stories**

* **US-1: View Topics**
    * As an English learner, I want to see a list of available topics (e.g., "Grammar," "Vocabulary," "Idioms") so I can choose what to focus on.

* **US-2: Daily Practice**
    * As an English learner, I want to practice 5 questions every day to build a consistent learning habit without feeling overwhelmed.

* **US-3: Extra Practice**
    * As an English learner, I want the option to practice more questions after I finish my daily set so I can study more when I have free time.

* **US-4: Answer Questions & Get Feedback**
    * As an English learner, I want to answer questions and get immediate feedback to understand my mistakes and learn from them.

* **US-5: Track Performance**
    * As an English learner, I want to see my score after a quiz session to track my progress.

* **US-6: View Statistics**
    * As an English learner, I want to view my overall learning statistics including daily progress, total questions answered, and accuracy rate.

* **US-7: Reliable Access**
    * As an English learner, I want the bot to work consistently even if there are issues with the Google Sheets connection.

---

## 3. Functional Requirements

### **3.1. Core Quiz Functionality**

* **FR-1: Content Sourcing**
    * The bot **must** fetch all quiz questions and their corresponding data from a designated Google Sheets file.
    * The Google Sheet will contain columns for `Topic`, `Question`, `Option A`, `Option B`, `Option C`, `Option D`, `Correct Answer`, and `Explanation`.
    * **FR-1a: CSV Fallback (Topic Directory)**: If Google Sheets is unavailable or misconfigured, the bot **must** automatically fallback to topic-based CSV files located in a `questions/` directory. Each file represents a topic (e.g., `questions/grammar.csv`) and includes columns: `Question`, `Option A`, `Option B`, `Option C`, `Option D`, `Correct Answer`, `Explanation`.
    * The bot **must** gracefully handle the transition between Google Sheets and per-topic CSV files without user intervention.

* **FR-2: Daily Quiz**
    * Each user is entitled to a daily quiz of **5 questions**.
    * The questions for the daily quiz should be selected randomly from the available topics in the Google Sheet.
    * The bot **must** track the completion of the daily quiz for each user.

* **FR-3: Additional Practice**
    * Once a user has completed their 5 daily questions, the bot **must** offer them the option to "Practice More".
    * Additional practice sessions will consist of sets of 5 random questions. There is no limit to how many additional sessions a user can take.

* **FR-4: Daily Reset**
    * The user's daily quiz status **must** reset every day at **midnight (00:00) UTC**.
    * The bot **must** include an automated scheduler that handles daily resets without manual intervention.
    * Users **must** have their daily progress reset automatically when they interact with the bot after midnight UTC.

### **3.2. User Interaction & Commands**

* **FR-5: `/start` Command**
    * Initiates interaction with the bot.
    * The bot will respond with a welcome message, a brief explanation of its features, and available commands.

* **FR-6: `/practice` Command**
    * Starts a new quiz session.
    * If the user has not completed their daily 5 questions, it starts the daily quiz.
    * If the user has already completed the daily quiz, it prompts them to start an additional practice session.

* **FR-7: `/topics` Command**
    * Displays a list of all unique topics available from the data source (Google Sheet or CSV).
    * Users can select a topic to practice questions specifically from that category.

* **FR-8: `/stats` Command**
    * Displays user's learning statistics including:
      - Daily progress (questions completed out of daily limit)
      - Total questions answered
      - Total correct answers
      - Overall accuracy percentage
      - Current daily quiz status

* **FR-9: Quiz Presentation & Feedback**
    * Questions **must** be presented using Telegram's native **Poll feature in "Quiz Mode"** with radio button options.
    * The poll **must** automatically show the correct answer and explanation after the user votes.
    * Users **must** receive additional feedback messages with detailed explanations when available.
    * **Fallback**: If polls fail, the bot **must** fallback to interactive inline keyboard buttons.
    * A final score summary **must** be provided at the end of each quiz session.

---

## 4. Non-functional Requirements

### **4.1. Technology Stack**

* **NFR-1: Language & Framework**
    * The bot will be built using the latest stable version of **Python** (3.8+).
    * The **`aiogram`** library will be used for interacting with the Telegram Bot API.
    * **`uv`** package manager will be used for modern Python dependency management.
    * The project **must** use `pyproject.toml` for dependency specification and project configuration.

* **NFR-2: Data Storage**
    * Primary quiz data will be stored and managed in **Google Sheets** with **CSV fallback** capability.
    * User state (e.g., daily quiz completion status, current score) will be managed using **SQLite database**.
    * The bot **must** maintain persistent user data across restarts.
    * Question data **must** be cached to improve performance and reduce API calls.

### **4.2. Performance & Reliability**

* **NFR-3: Response Time**
    * The bot's response time to any user interaction should be under 3 seconds.

* **NFR-4: Uptime**
    * The bot should be available and operational 99.5% of the time.

* **NFR-5: Error Handling & Reliability**
    * The bot must gracefully handle failures, such as an inability to connect to the Google Sheets API.
    * **Automatic fallback**: The bot **must** seamlessly switch to CSV data source when Google Sheets is unavailable.
    * The bot **must** continue operating with basic functionality even if some features fail.
    * Comprehensive logging **must** be implemented for debugging and monitoring purposes.
    * Users **must** receive helpful error messages without technical details.

### **4.3. Security**

* **NFR-6: Credentials**
    * All API tokens and credentials (Telegram Bot API Token, Google Sheets API credentials) **must not** be hardcoded. They should be managed securely using environment variables or a secrets management tool.
    * **Optional configuration**: Google Sheets credentials **may** be optional, allowing the bot to operate with CSV fallback only.

---

## 5. Implementation Requirements

### **5.1. Architecture Components**

* **IR-1: Modular Design**
    * The bot **must** be implemented with a modular architecture separating concerns:
      - `bot.py`: Main bot implementation and command handlers
      - `config.py`: Configuration management
      - `database.py`: User state and data persistence
      - `google_sheets.py`: Data source integration with fallback logic
      - `quiz_logic.py`: Quiz session management and scoring
      - `scheduler.py`: Automated daily reset functionality

* **IR-2: Session Management**
    * The bot **must** maintain active quiz sessions in memory
    * Each user **must** be able to have only one active session at a time
    * Sessions **must** be properly cleaned up after completion or timeout

* **IR-3: Data Models**
    * User state **must** be tracked with the following attributes:
      - Daily questions completed
      - Last daily reset timestamp
      - Total questions answered
      - Total correct answers
      - Current quiz session state
    * Quiz sessions **must** track:
      - Session type (daily/practice)
      - Selected topic (if any)
      - Current question index
      - User answers and scores

### **5.2. Deployment & Operations**

* **IR-4: Startup Requirements**
    * The bot **must** validate required configuration on startup
    * Missing Google Sheets configuration **must not** prevent bot startup
    * A startup script **should** be provided for easy deployment
    * Dependency installation **must** be automated using uv

* **IR-5: Monitoring & Logging**
    * All major operations **must** be logged with appropriate levels
    * Error conditions **must** be logged with sufficient detail for debugging
    * Data source switching (Google Sheets ↔ CSV) **must** be logged
    * User interactions **should** be logged for analytics purposes