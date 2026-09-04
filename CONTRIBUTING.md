# Contributing to Kuberbolt

First off, thank you for considering contributing to Kuberbolt! It's people like you that make Kuberbolt such a great tool.

## Development Setup

To set up your local development environment:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/kuberbolt.git
   cd kuberbolt
   ```

2. **Backend (Python & Go):**
   - Ensure you have **Python 3.12+** and **Go 1.21+** installed.
   - For Python development, it's recommended to create a virtual environment:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Infrastructure:**
   - Kuberbolt relies on LND and Docker. Ensure Docker and Docker Compose are installed and running.

For a comprehensive guide on setting up the local environment, please refer to our [Local Dev Setup Guide](docs/local-dev-setup.md).

## Running Tests

Before submitting a pull request, ensure all tests pass.

- **Python Tests (SDK & API):**
  Ensure you are in the project root directory and run `pytest`:
  ```bash
  pytest
  ```

- **Go Tests (Gateway):**
  Navigate to the gateway directory and run `go test`:
  ```bash
  cd gateway
  go test ./...
  ```

## Pull Request Process

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Update the documentation if your changes require it.
4. Ensure your code conforms to our linting standards (e.g., `flake8`/`black` for Python, `gofmt` for Go).
5. Issue that pull request! Please provide a clear and descriptive PR message explaining the "why" and "what" of your changes.
