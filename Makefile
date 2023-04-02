components:=partitioner uploader
code_dirs:=$(components) stacks bin
repo_name:=file-uploader
default_branch:=main

# Docker
.PHONY: up
up: create-dev-env
	@docker compose up --build -d

.PHONY: down
down:
	@docker compose down -v

.PHONY: create-dev-env
create-dev-env:
	@test -e .env || cp .env.example .env

# Code
.PHONY: ci-deploy
ci-deploy: create-ci-env
	@docker-compose run --rm deployer make deploy

.PHONY: deploy
deploy: build
	@cdk deploy file-uploader --require-approval never

.PHONY: deploy-pipeline
deploy-pipeline: build
	@cdk context --clear
	@cdk bootstrap aws://${CDK_DEFAULT_ACCOUNT}/${AWS_DEFAULT_REGION}
	@cdk deploy file-uploader-source-code --require-approval never
	@$(MAKE) push-code
	@cdk deploy file-uploader-pipeline --require-approval never

.PHONY: push-code
push-code:
	@git config --global credential.helper "!aws codecommit credential-helper $$@"
	@git config --global credential.UseHttpPath true
	@git push https://git-codecommit.${AWS_DEFAULT_REGION}.amazonaws.com/v1/repos/${repo_name} $(shell git branch --show-current):${default_branch}

.PHONY: create-ci-env
create-ci-env:
	@rm -f .env
	@role=$$(curl 169.254.170.2$${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}); \
	  echo "AWS_ACCESS_KEY_ID=$$(echo $$role | jq -r '.AccessKeyId')" >> .env; \
	  echo "AWS_SECRET_ACCESS_KEY=$$(echo $$role | jq -r '.SecretAccessKey')" >> .env; \
	  echo "AWS_SESSION_TOKEN=$$(echo $$role | jq -r '.Token')" >> .env; \
	  echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}" >> .env; \
	  echo "CDK_DEFAULT_ACCOUNT=$$(aws sts get-caller-identity | jq -r '.Account')" >> .env

.PHONY: build
build: lint build-lambda

.PHONY: build-lambda
build-lambda: $(components)
	@for c in $^; do $(MAKE) build -C $$c; done

.PHONY: test
test: lint test-apps

.PHONY: test-apps
test-apps: $(components)
	@for c in $^; do $(MAKE) test -C $$c; done

.PHONY: lint
lint: format
	@flake8 $(code_dirs)

.PHONY: format
format:
	@isort $(code_dirs)
	@black $(code_dirs)
