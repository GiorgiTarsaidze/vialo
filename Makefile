.PHONY: layer clean-layer test lint typecheck validate build check

SAM := uvx --from aws-sam-cli==1.165.0 sam

# Build and verify the Lambda dependency layer
layer: backend/layer/python
	./backend/verify-layer.sh

backend/layer/python: backend/pyproject.toml backend/uv.lock backend/build-layer.sh
	@echo "==> Building Lambda dependency layer..."
	./backend/build-layer.sh

clean-layer:
	rm -rf backend/layer/python backend/layer/requirements.txt

# Run backend tests
test:
	cd backend && uv run pytest --cov=vialo --cov-report=term-missing -x

# Run linting
lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .

# Run type checking
typecheck:
	cd backend && uv run mypy src tests

# Validate SAM template
validate:
	$(SAM) validate --lint --template-file infra/template.yaml

# Build SAM application
build: layer
	$(SAM) build --template-file infra/template.yaml

# Run all checks
check: lint typecheck test validate
