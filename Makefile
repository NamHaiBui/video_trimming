# Video Trimming Service Makefile

.PHONY: help build push deploy logs shell test clean

# Configuration
AWS_REGION ?= us-east-1
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY ?= video-trimming
ECS_CLUSTER ?= video-processing-cluster
ECS_SERVICE ?= video-trimming-service
IMAGE_TAG ?= latest

# Derived variables
ECR_URI = $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPOSITORY)

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t $(ECR_REPOSITORY):$(IMAGE_TAG) .
	docker tag $(ECR_REPOSITORY):$(IMAGE_TAG) $(ECR_URI):$(IMAGE_TAG)

ecr-login: ## Login to ECR
	@echo "Logging into ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URI)

push: build ecr-login ## Build and push image to ECR
	@echo "Pushing image to ECR..."
	docker push $(ECR_URI):$(IMAGE_TAG)

deploy: push ## Deploy to ECS
	@echo "Registering new task definition..."
	aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json --region $(AWS_REGION)
	@echo "Updating ECS service..."
	aws ecs update-service --cluster $(ECS_CLUSTER) --service $(ECS_SERVICE) --force-new-deployment --region $(AWS_REGION)

logs: ## View ECS service logs
	@echo "Fetching recent logs..."
	aws logs tail /ecs/video-trimming --follow --region $(AWS_REGION)

status: ## Check ECS service status
	@echo "Checking service status..."
	aws ecs describe-services --cluster $(ECS_CLUSTER) --services $(ECS_SERVICE) --region $(AWS_REGION) --query 'services[0].{Status:status,RunningCount:runningCount,DesiredCount:desiredCount,TaskDefinition:taskDefinition}'

shell: ## Run container shell locally
	docker run -it --rm --env-file .env $(ECR_REPOSITORY):$(IMAGE_TAG) /bin/bash

test: ## Run tests locally
	docker run --rm --env-file .env $(ECR_REPOSITORY):$(IMAGE_TAG) python -m pytest src/tests/ -v

local-run: ## Run application locally with Docker Compose
	docker-compose up --build

local-stop: ## Stop local Docker Compose
	docker-compose down

clean: ## Clean up Docker images
	docker rmi $(ECR_REPOSITORY):$(IMAGE_TAG) $(ECR_URI):$(IMAGE_TAG) 2>/dev/null || true
	docker system prune -f

setup-params: ## Setup AWS SSM parameters (requires manual configuration)
	@echo "Setting up AWS SSM parameters..."
	@echo "Please configure the following parameters in AWS Systems Manager:"
	@echo "  /video-trimming/sqs-queue-url"
	@echo "  /video-trimming/podcast-metadata-table"
	@echo "  /video-trimming/quotes-table"
	@echo "  /video-trimming/chunk-table"
	@echo "  /video-trimming/video-bucket"
	@echo "  /video-trimming/summary-transcript-bucket"
	@echo "  /video-trimming/video-quotes-chunk-bucket"
	@echo "  /video-trimming/chunk-video-bucket"
	@echo "  /video-trimming/video-summary-bucket"

validate: ## Validate task definition
	@echo "Validating ECS task definition..."
	aws ecs validate-task-definition --cli-input-json file://ecs-task-definition.json --region $(AWS_REGION)

info: ## Show deployment information
	@echo "Deployment Information:"
	@echo "  AWS Account ID: $(AWS_ACCOUNT_ID)"
	@echo "  AWS Region: $(AWS_REGION)"
	@echo "  ECR Repository: $(ECR_URI)"
	@echo "  ECS Cluster: $(ECS_CLUSTER)"
	@echo "  ECS Service: $(ECS_SERVICE)"
	@echo "  Image Tag: $(IMAGE_TAG)"

# SSL/TLS troubleshooting
fix-ssl: ## Diagnose and fix SSL/TLS issues
	@echo "🔍 Running SSL diagnostics and fixes..."
	python scripts/fix_ssl_issues.py --apply-fixes

check-ssl: ## Check SSL/TLS configuration only
	@echo "🔍 Checking SSL configuration..."
	python scripts/fix_ssl_issues.py --check-only

update-deps: ## Update SSL-related dependencies
	@echo "📦 Updating SSL-related dependencies..."
	pip install --upgrade urllib3>=1.26.18,<3.0.0 certifi requests boto3 botocore
