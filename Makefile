components:=partitioner uploader
code_dirs:=$(components) stacks bin

# Docker
.PHONY: up
up:
	@docker compose up --build -d

.PHONY: down
down:
	@docker compose down -v

# Code
.PHONY: ci-deploy
ci-deploy:
	@docker compose run --rm deployer make deploy

.PHONY: deploy
deploy: build
	@cdk context --clear
	@cdk bootstrap aws://${CDK_DEFAULT_ACCOUNT}/${AWS_DEFAULT_REGION}
	@cdk deploy FileUploader --require-approval never

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
