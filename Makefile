# HappyOS Multi-Agent System Makefile
# AWS AI Agent Global Hackathon 2025

.PHONY: help install dev prod test clean docker-build docker-run agents backend frontend demo

# Default environment
ENV ?= dev
REGION ?= us-east-1

help: ## Show this help message
	@echo "🚀 HappyOS Multi-Agent System - AWS Hackathon 2024"
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === DEVELOPMENT COMMANDS ===

install: ## Install all dependencies
	@echo "📦 Installing dependencies..."
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	pip install -r requirements.txt  # Root HappyOS SDK dependencies

dev: ## Start development environment
	@echo "🚀 Starting HappyOS development environment..."
	docker-compose up -d

dev-logs: ## View development logs
	docker-compose logs -f

dev-stop: ## Stop development environment
	docker-compose down

# === AGENT COMMANDS ===

agents: ## Start all MCP agents
	@echo "🤖 Starting all MCP agents..."
	docker run -d -p 8001:8001 --name agent-svea agent-svea-mcp-server
	docker run -d -p 8002:8002 --name felicias-finance finance-mcp-server
	docker run -d -p 8003:8003 --name meetmind meetmind-mcp-server

agent-svea: ## Start Agent Svea (Swedish compliance)
	@echo "🇸🇪 Starting Agent Svea..."
	cd agent_svea && python svea_mcp_server.py

agent-finance: ## Start Felicia's Finance
	@echo "💰 Starting Felicia's Finance..."
	cd felicias_finance && python finance_mcp_server.py

agent-meetmind: ## Start MeetMind
	@echo "🎯 Starting MeetMind..."
	cd meetmind && python summarizer_mcp_server.py

# === BACKEND COMMANDS ===

backend: ## Start backend server
	@echo "⚙️ Starting HappyOS backend..."
	cd backend && python main.py

backend-test: ## Run backend tests
	cd backend && python -m pytest tests/ -v

# === FRONTEND COMMANDS ===

frontend: ## Start frontend development server
	@echo "🌐 Starting frontend..."
	cd frontend && npm start

frontend-build: ## Build frontend for production
	cd frontend && npm run build

# === PRODUCTION DEPLOYMENT ===

prod: ## Deploy production environment
	@echo "🚀 Deploying HappyOS to production..."
	docker-compose -f docker-compose.prod.yml up -d

prod-logs: ## View production logs
	docker-compose -f docker-compose.prod.yml logs -f

prod-stop: ## Stop production environment
	docker-compose -f docker-compose.prod.yml down

# === DEMO COMMANDS ===

demo: ## Start complete demo environment
	@echo "🎬 Starting HappyOS hackathon demo..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ Demo running at:"
	@echo "   Frontend: http://localhost:3000"
	@echo "   Backend:  http://localhost:8000"
	@echo "   Agent Svea: http://localhost:8001"
	@echo "   Felicia's Finance: http://localhost:8002"
	@echo "   MeetMind: http://localhost:8003"

demo-test: ## Test cross-agent workflow
	@echo "🧪 Testing cross-agent MCP workflow..."
	curl -X POST http://localhost:8000/mcp/workflow/compliance \
		-H "Content-Type: application/json" \
		-d '{"meeting_id": "hackathon_demo", "tenant_id": "aws_hackathon"}'

demo-outage: ## Simulate AWS outage for resilience demo
	@echo "⚠️ Simulating AWS outage..."
	curl -X POST http://localhost:8000/admin/simulate-outage \
		-H "Content-Type: application/json" \
		-d '{"services": ["bedrock", "sagemaker"], "duration": 300}'

# === TESTING COMMANDS ===

test: ## Run all tests
	@echo "🧪 Running HappyOS test suite..."
	python -m pytest tests/ -v
	cd backend && python -m pytest tests/ -v

test-sdk: ## Test HappyOS SDK
	python -m pytest tests/test_base_agent.py -v
	python -m pytest tests/test_mcp_server_manager.py -v
	python -m pytest tests/test_agent_configuration.py -v

test-performance: ## Run performance tests
	python -m pytest tests/test_performance.py -v -m performance

test-integration: ## Run integration tests
	python -m pytest tests/ -v -m integration

# === DOCKER COMMANDS ===

docker-build: ## Build all Docker images
	@echo "🐳 Building Docker images..."
	docker build -t happy-os-backend -f Dockerfile.backend .
	docker build -t agent-svea-mcp-server -f agent_svea/Dockerfile agent_svea/
	docker build -t finance-mcp-server -f felicias_finance/Dockerfile felicias_finance/
	docker build -t meetmind-mcp-server -f meetmind/Dockerfile meetmind/

docker-run: ## Run complete system in Docker
	docker-compose -f docker-compose.prod.yml up -d

docker-clean: ## Clean Docker containers and images
	docker-compose down -v
	docker system prune -f

# === AWS DEPLOYMENT ===

aws-deploy: ## Deploy to AWS (requires AWS credentials)
	@echo "☁️ Deploying to AWS..."
	cd backend/infrastructure/aws/iac && python scripts/deploy.py deploy --environment $(ENV) --region $(REGION)

aws-destroy: ## Destroy AWS infrastructure
	cd backend/infrastructure/aws/iac && python scripts/deploy.py destroy --environment $(ENV) --region $(REGION)

# === MONITORING COMMANDS ===

logs: ## View system logs
	@echo "📋 Viewing system logs..."
	tail -f backend/logs/*.log

metrics: ## View MCP metrics
	curl -s http://localhost:8000/metrics/mcp-flow | jq .

health: ## Check system health
	@echo "🏥 Checking system health..."
	@echo "Backend:" && curl -s http://localhost:8000/health || echo "❌ Backend down"
	@echo "Agent Svea:" && curl -s http://localhost:8001/health || echo "❌ Agent Svea down"
	@echo "Felicia's Finance:" && curl -s http://localhost:8002/health || echo "❌ Finance down"
	@echo "MeetMind:" && curl -s http://localhost:8003/health || echo "❌ MeetMind down"

# === UTILITY COMMANDS ===

clean: ## Clean generated files and caches
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf test_reports/ 2>/dev/null || true

lint: ## Lint code
	@echo "🔍 Linting code..."
	flake8 backend/ happyos/ tests/ --max-line-length=120
	cd frontend && npm run lint

format: ## Format code
	@echo "✨ Formatting code..."
	black backend/ happyos/ tests/
	cd frontend && npm run format

# === HACKATHON SPECIFIC ===

hackathon-setup: ## Complete hackathon setup
	@echo "🏆 Setting up HappyOS for AWS Hackathon demo..."
	$(MAKE) install
	$(MAKE) docker-build
	$(MAKE) demo
	@echo "🎉 Hackathon demo ready!"

hackathon-demo: ## Run hackathon demonstration
	@echo "🎬 Running hackathon demonstration..."
	$(MAKE) demo-test
	@echo "🎯 Testing resilience..."
	$(MAKE) demo-outage
	@echo "📊 Checking metrics..."
	$(MAKE) metrics

# === ENVIRONMENT SHORTCUTS ===

dev-full: ## Full development setup
	$(MAKE) install && $(MAKE) dev

prod-full: ## Full production deployment
	$(MAKE) docker-build && $(MAKE) prod

# === STATUS ===

status: ## Show system status
	@echo "📊 HappyOS System Status:"
	@echo "Environment: $(ENV)"
	@echo "Region: $(REGION)"
	@$(MAKE) health
