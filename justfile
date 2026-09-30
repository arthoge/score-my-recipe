# Developer commands for Score My Recipe

# prefer bash
set shell := ["bash", "-uc"]
# load dot env
set dotenv-load := true
set dotenv-required := true

just_frontend := "cd frontend && just"
just_server := "cd server && just"

# this help
[default]
help:
    @just --list
    @echo
    @echo Also look at server and frontend folder for more recipes
    @echo

# ===========================================
# SETUP
# ===========================================

# Full project setup (server + frontend)
[group('setup')]
setup:
    @echo "=== Setting up project ==="
    scripts/dev-setup.sh full

# Refresh dependencies
[group('setup')]
refresh:
  {{ just_frontend }} refresh
  {{ just_server }} refresh

# ===========================================
# PROD
# ===========================================

[group('prod')]
create_external_volumes:
    docker volume create --name $COMPOSE_PROJECT_NAME-server_data || true

# ===========================================
# DEVELOPMENT
# ===========================================

# Run backend dev server only
[group('dev')]
dev-server:
    {{ just_server }} dev

# Run frontend dev server only
[group('dev')]
dev-frontend:
    {{ just_frontend }} dev

# Regenerate OpenAPI spec
[group('dev')]
generate-openapi suffix='':
    cd server && uv run typer api/cli.py run export-openapi ../docs/openapi{{ suffix }}.json
    # generate typescript file with openapi-typescript
    docker run --rm -v $(pwd)/docs/openapi{{ suffix }}.json:/openapi.json -v $(pwd)/frontend/src:/src courtapi/openapi-typescript:7.13.0 /openapi.json -o /src/api-schema{{ suffix }}.d.ts
    # use same image to fix ownership of generated file
    docker run --rm --entrypoint /bin/sh -v $(pwd)/frontend/src:/src courtapi/openapi-typescript:7.13.0 -c "chown $(id -u):$(id -g) /src/api-schema{{ suffix }}.d.ts"
    {{ just_frontend }} lint-one src/api-schema{{ suffix }}.d.ts



# ===========================================
# QUALITY
# ===========================================

# Linting
[group('quality')]
lint:
    @echo "::group::Server lint"
    {{ just_server }} lint
    @echo "::endgroup::"
    @echo "::group::Frontend lint"
    {{ just_frontend }} lint
    @echo "::endgroup::"

# Quality Checks
[group('quality')]
check:
    @echo "::group::Server check"
    {{ just_server }} check
    @echo "::endgroup::"
    @echo "::group::Frontend check"
    {{ just_frontend }} check
    @echo "::endgroup::"
    @echo "::group::openapi check"
    @just check-openapi
    @echo "::endgroup::"

check-openapi:
    @just generate-openapi "-check"
    diff docs/openapi.json docs/openapi-check.json || (echo "OpenAPI spec has changed. Please run 'just generate-openapi' to update it." && exit 1)
    diff frontend/src/api-schema.d.ts frontend/src/api-schema-check.d.ts || (echo "TypeScript API schema has changed. Please run 'just generate-openapi' to update it." && exit 1)
    rm -f docs/openapi-check.json frontend/src/api-schema-check.d.ts

# Run all tests
[group('quality')]
test:
    {{ just_server }} test
    {{ just_frontend }} test
