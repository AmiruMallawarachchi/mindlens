# Contributing to MindLens

Thank you for your interest in MindLens! This project is my Final Year Project at Cardiff Metropolitan University, but I welcome contributions that improve the codebase, documentation, or user experience.

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB (local or Atlas)
- Git

### Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/mindlens.git`
3. Create a feature branch: `git checkout -b feat/your-feature-name`
4. Follow backend + frontend setup in README.md
5. Make your changes
6. Run tests: `pytest tests/unit/ -v`
7. Run linting: `black backend/ && ruff check backend/`
8. Commit with conventional format: `feat(scope): description`
9. Push and submit a PR

## 📝 Contribution Guidelines

### Code Style
- Python: Black formatter, Ruff linter, MyPy type checking
- TypeScript: ESLint + Prettier
- Max line length: 88 characters (Black default)
- Type hints required for all public functions

### Testing
- Unit tests for every new feature
- Integration tests for API changes
- Security tests for authentication changes
- Target: 85%+ coverage

### Documentation
- Update README.md if adding features
- Update docs/API.md for new endpoints
- Add docstrings to all public methods
- Update CHANGELOG.md

### Security
- Never commit secrets (API keys, passwords)
- Use `.env.example` for new environment variables
- Report security issues privately (see SECURITY.md)
- Ensure PII handling for new features

## 🏷️ Commit Convention
feat(scope): add new feature
fix(scope): fix a bug
docs(scope): update documentation
test(scope): add or update tests
refactor(scope): code change without behavior change
chore(scope): maintenance tasks
security(scope): security improvements

## 🙏 Code of Conduct

Please read our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## 💬 Questions?

- Open a [GitHub Discussion](https://github.com/AmiruMallawarachchi/mindlens/discussions)
- Email: amiru.mallawarachchi@example.com