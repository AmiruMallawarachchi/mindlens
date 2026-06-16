# Changelog

All notable changes to MindLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 3 agents: orchestrator, empathy, mindfulness, crisis (templates)
- Emotional Operating System (EOS) with 28-class emotion detection
- 3-layer safety gate: Regex + DistilBERT + FAISS
- Session memory with 10-turn buffer
- Longitudinal memory with people graph

## [0.2.0] - 2026-06-16

### Added
- Multi-agent orchestrator with asyncio.gather parallel inference
- Empathy agent with Groq 8B/70B dual-tier routing
- Mindfulness agent with LLM-generated exercises
- Crisis agent with template-only responses (ZERO LLM)
- Safety gate with 3-layer detection (threshold: 0.45)
- Emotional Operating System (EOS) state model
- Session memory with rolling summarization
- Longitudinal memory with mood trends and people graph
- FastAPI backend with lifespan management
- MongoDB connection with Motor async driver
- Pydantic v2 configuration management
- GitHub issue templates, PR template, CODEOWNERS
- MIT LICENSE
- SECURITY.md with vulnerability reporting policy
- CONTRIBUTING.md with setup guidelines
- CODE_OF_CONDUCT.md

### Changed
- Migrated from sequential to parallel model inference
- Updated crisis threshold to 0.45 (maximize recall)

### Security
- Added PII stripping before every model call
- JWT in httpOnly cookies (never localStorage)
- Rate limiting planned for all endpoints

## [0.1.0] - 2026-04-15

### Added
- 3 trained transformer models:
  - Crisis detection: DistilBERT fine-tuned on 230k samples
  - Emotion classification: RoBERTa go-emotions 28-class
  - Mental health: MentalBERT 5-label classifier
- Data cleaning pipelines for all datasets
- Jupyter notebooks for model training and evaluation
- Basic FastAPI skeleton with health checks
- MongoDB connection setup