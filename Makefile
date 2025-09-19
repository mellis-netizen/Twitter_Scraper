# Crypto TGE Monitor Makefile

.PHONY: help install setup test run-once run-continuous status clean

help: ## Show this help message
	@echo "Crypto TGE Monitor - Available Commands:"
	@echo "========================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

setup: ## Run initial setup
	python setup.py

test: ## Test the system
	python test_system.py

run-once: ## Run monitoring once
	python run.py --mode once

run-continuous: ## Run monitoring continuously
	python run.py --mode continuous

run-test: ## Test all components
	python run.py --mode test

status: ## Show system status
	python run.py --mode status

clean: ## Clean up logs and temporary files
	rm -rf logs/*.log
	rm -rf logs/*.json
	rm -rf __pycache__
	rm -rf src/__pycache__
	find . -name "*.pyc" -delete

logs: ## Show recent logs
	tail -f logs/crypto_monitor.log

check-env: ## Check environment configuration
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "✅ .env file found"
	@echo "📧 Email configured: $$(grep -q 'EMAIL_USER=' .env && echo 'Yes' || echo 'No')"
	@echo "🐦 Twitter configured: $$(grep -q 'TWITTER_API_KEY=' .env && echo 'Yes' || echo 'No')"

quick-start: setup check-env test ## Quick start: setup, check config, and test
	@echo "🚀 Quick start completed!"
	@echo "Run 'make run-once' to test monitoring or 'make run-continuous' to start monitoring"

dev: ## Development mode with verbose logging
	python run.py --mode continuous --verbose

