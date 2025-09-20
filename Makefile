# Quiz Telegram Bot - Makefile
# Useful automation for local dev, Docker, and CI

# ------- Configuration -------
APP            ?= bot.py
IMAGE          ?= quiz-telegram-bot:latest
CONTAINER      ?= quiz-telegram-bot
DATA_DIR       ?= data
QUESTIONS_DIR  ?= questions
PY             ?= uv run
UV             ?= uv

# Export variables from .env if present (simple parser: KEY=VALUE, ignores comments)
ifneq (,$(wildcard .env))
include .env
export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
endif

# ------- Help -------
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make sync              - Install/resolve Python deps with uv"
	@echo "  make run               - Run the bot locally (uv run)"
	@echo "  make env               - Create .env from env.example if missing"
	@echo "  make check             - Validate env and questions directory"
	@echo "  make fmt               - Format code (black, isort)"
	@echo "  make lint              - Lint code (flake8)"
	@echo "  make test              - Run tests (pytest)"
	@echo "  make clean             - Remove caches and build artifacts"
	@echo "  make clean-data        - Remove SQLite data files"
	@echo "  make docker-build      - Build Docker image ($(IMAGE))"
	@echo "  make docker-run        - Run container (auto-detects VPS/local)"
	@echo "  make docker-run-volume - Run container with Docker volume"
	@echo "  make docker-stop       - Stop container"
	@echo "  make docker-rm         - Remove container"
	@echo "  make docker-logs       - Tail container logs"
	@echo "  make compose-up        - Up with docker-compose"
	@echo "  make compose-down      - Down with docker-compose"
	@echo "  make compose-logs      - Tail compose logs"

# ------- Local dev -------
.PHONY: sync
sync:
	@command -v $(UV) >/dev/null 2>&1 || { echo "\nuv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh\n"; exit 1; }
	$(UV) sync

.PHONY: run
run: check sync
	$(PY) $(APP)

.PHONY: env
env:
	@test -f .env || cp env.example .env
	@echo ".env is ready (edit TELEGRAM_BOT_TOKEN and other settings if needed)."

.PHONY: check
check:
	@test -f .env || { echo "❌ .env missing. Run 'make env' and set TELEGRAM_BOT_TOKEN"; exit 1; }
	@test -d $(QUESTIONS_DIR) || { echo "❌ '$(QUESTIONS_DIR)' directory missing"; exit 1; }
	@cnt=$$(find $(QUESTIONS_DIR) -name '*.csv' | wc -l); \
	 if [ "$$cnt" -eq 0 ]; then echo "❌ No CSV files in $(QUESTIONS_DIR)"; exit 1; fi; \
	 echo "✅ Found $$cnt CSV files in $(QUESTIONS_DIR)"

.PHONY: fmt
fmt:
	$(PY) -m isort .
	$(PY) -m black .

.PHONY: lint
lint:
	$(PY) -m flake8 .

.PHONY: test
test:
	$(PY) -m pytest -q

.PHONY: clean
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov \
	       build dist *.egg-info __pycache__ .uv
	find . -name "__pycache__" -type d -exec rm -rf {} + || true
	find . -name "*.pyc" -delete || true

.PHONY: clean-data
clean-data:
	rm -rf $(DATA_DIR)/*.db $(DATA_DIR)/*.sqlite $(DATA_DIR)/*.sqlite3 quiz_bot.db || true

# ------- Docker -------
.PHONY: docker-build
docker-build:
	docker build \
	  --build-arg UID=$$(id -u) \
	  --build-arg GID=$$(id -g) \
	  -t $(IMAGE) .

.PHONY: docker-run
docker-run: docker-rm
	@mkdir -p $(DATA_DIR)
	@# Try to set permissions, fall back to root user if permission denied
	@if chown -R $$(id -u):$$(id -g) $(DATA_DIR) 2>/dev/null && chmod 775 $(DATA_DIR) 2>/dev/null; then \
		echo "Setting container user to $$(id -u):$$(id -g)"; \
		USER_ARG="--user $$(id -u):$$(id -g)"; \
		VOLUME_ARG=":Z"; \
	else \
		echo "Permission denied - running as root (VPS mode)"; \
		USER_ARG="--user root"; \
		VOLUME_ARG=""; \
	fi; \
	docker run -d \
	  --name $(CONTAINER) \
	  --restart unless-stopped \
	  $$USER_ARG \
	  -e TELEGRAM_BOT_TOKEN=$${TELEGRAM_BOT_TOKEN} \
	  -e QUESTIONS_DIRECTORY=/app/$(QUESTIONS_DIR) \
	  -e DATABASE_PATH=/app/$(DATA_DIR)/quiz_bot.db \
	  -v $$(pwd)/$(QUESTIONS_DIR):/app/$(QUESTIONS_DIR):ro \
	  -v $$(pwd)/$(DATA_DIR):/app/$(DATA_DIR)$$VOLUME_ARG \
	  $(IMAGE)

# Alternative with docker volume
.PHONY: docker-run-volume
docker-run-volume: docker-rm
	docker volume create quiz-bot-data || true
	docker run -d \
	  --name $(CONTAINER) \
	  --restart unless-stopped \
	  -e TELEGRAM_BOT_TOKEN=$${TELEGRAM_BOT_TOKEN} \
	  -e QUESTIONS_DIRECTORY=/app/$(QUESTIONS_DIR) \
	  -e DATABASE_PATH=/app/data/quiz_bot.db \
	  -v $$(pwd)/$(QUESTIONS_DIR):/app/$(QUESTIONS_DIR):ro \
	  -v quiz-bot-data:/app/data \
	  $(IMAGE)

.PHONY: docker-stop
docker-stop:
	-@docker stop $(CONTAINER) >/dev/null 2>&1 || true

.PHONY: docker-rm
docker-rm: docker-stop
	-@docker rm $(CONTAINER) >/dev/null 2>&1 || true

.PHONY: docker-logs
docker-logs:
	docker logs -f $(CONTAINER)

# ------- Docker Compose -------
.PHONY: compose-up
compose-up:
	docker compose up -d --build

.PHONY: compose-down
compose-down:
	docker compose down

.PHONY: compose-logs
compose-logs:
	docker compose logs -f
