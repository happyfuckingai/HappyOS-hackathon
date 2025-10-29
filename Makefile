# Infrastructure Recovery CDK Makefile

.PHONY: help install bootstrap synth deploy destroy validate clean

# Default environment
ENV ?= dev
REGION ?= us-east-1

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	cd backend/infrastructure/aws/iac && pip install -r requirements.txt
	npm install -g aws-cdk

bootstrap: ## Bootstrap CDK
	cd backend/infrastructure/aws/iac && python scripts/deploy.py bootstrap --environment $(ENV) --region $(REGION)

synth: ## Synthesize CDK templates
	cd backend/infrastructure/aws/iac && python scripts/deploy.py synth --environment $(ENV) --region $(REGION)

deploy: ## Deploy infrastructure
	cd backend/infrastructure/aws/iac && python scripts/deploy.py deploy --environment $(ENV) --region $(REGION)

deploy-bg: ## Deploy using blue-green strategy
	cd backend/infrastructure/aws/iac && python scripts/blue_green_deploy.py --environment $(ENV) --region $(REGION)

destroy: ## Destroy infrastructure
	cd backend/infrastructure/aws/iac && python scripts/deploy.py destroy --environment $(ENV) --region $(REGION)

validate: ## Validate deployment
	cd backend/infrastructure/aws/iac && python scripts/deploy.py validate --environment $(ENV) --region $(REGION)

diff: ## Show CDK diff
	cd backend/infrastructure/aws/iac && cdk diff --context environment=$(ENV)

clean: ## Clean generated files
	cd backend/infrastructure/aws/iac && rm -f outputs-*.json deployment-*.json
	cd backend/infrastructure/aws/iac && rm -rf cdk.out/

lint: ## Lint Python code
	cd backend/infrastructure/aws/iac && flake8 . --max-line-length=120
	cd backend/infrastructure/aws/iac && black --check .

format: ## Format Python code
	cd backend/infrastructure/aws/iac && black .

security-scan: ## Run security scan
	cd backend/infrastructure/aws/iac && bandit -r . -f json -o security-report.json

# Environment-specific shortcuts
dev-deploy: ## Deploy to dev environment
	$(MAKE) deploy ENV=dev

staging-deploy: ## Deploy to staging environment
	$(MAKE) deploy ENV=staging

prod-deploy: ## Deploy to production environment (blue-green)
	$(MAKE) deploy-bg ENV=prod

# Rollback commands
rollback: ## Rollback deployment (requires BACKUP_ID)
	@if [ -z "$(BACKUP_ID)" ]; then echo "Error: BACKUP_ID is required"; exit 1; fi
	cd backend/infrastructure/aws/iac && python scripts/deploy.py rollback --environment $(ENV) --backup-id $(BACKUP_ID)

# Monitoring commands
logs: ## View CloudWatch logs
	aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/infra-recovery-$(ENV)"

metrics: ## View CloudWatch metrics
	aws cloudwatch list-metrics --namespace "AWS/Lambda" --dimensions Name=FunctionName,Value=infra-recovery-$(ENV)

# Development commands
local-test: ## Run local tests
	cd backend && python -m pytest tests/

docker-build: ## Build Docker images
	docker build -t infra-recovery-backend -f Dockerfile.backend .

docker-run: ## Run backend in Docker
	docker run -p 8000:8000 infra-recovery-backend