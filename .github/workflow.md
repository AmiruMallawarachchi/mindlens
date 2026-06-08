# MindLens Git Workflow

> **Project:** MindLens — Multi-Agent Agentic AI for Mental Health  
> **Developer:** Amiru Umavin Mallawa Arachchi  
> **Deadline:** August 11, 2026  
> **Current Date:** June 6, 2026  
> **Branching Model:** Git Flow (simplified for solo developer)  

---

## 1. Branch Strategy

We use a **three-tier branch model** designed for a solo developer who still needs clean history, safe rollbacks, and viva-ready releases.

```
main        ← production-stable, tagged releases only
    ↑
dev         ← integration branch, working but deployable
    ↑
feat/*      ← one branch per feature/file group
hotfix/*    ← emergency fixes (branched from main)
```

### Branch Rules

| Branch | Purpose | Merge Target | Protection |
|--------|---------|------------|------------|
| `main` | Viva-ready, deployable snapshots | — | Never commit directly. Only accept merges from `dev` or `hotfix/*`. Tag every merge. |
| `dev` | Daily integration. All features land here first. | `main` | Commit freely, but keep it compiling/running. |
| `feat/name` | One logical feature per branch. | `dev` | Delete after merge. |
| `hotfix/name` | Critical bug in `main`. | `main` AND `dev` | Delete after merge. |

### Naming Convention

```
feat/phase3-memory-system
feat/phase3-rag-pipeline
feat/phase3-empathy-agent
feat/phase4-dashboard-ui
feat/phase4-websocket-chat
hotfix/crisis-threshold-bug
```

**Rule:** If a branch touches more than 3 logical files, the scope is too broad. Split it.

---

## 2. Commit Convention (Conventional Commits)

Every commit message must follow this format. It auto-generates changelogs and keeps your viva history professional.

```
<type>(<scope>): <short description>

<body>          ← optional but encouraged for learning
<footer>        ← optional: issue refs, breaking changes
```

### Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New file, new agent, new endpoint | `feat(agents): add empathy_agent with template validation` |
| `fix` | Bug fix, correction | `fix(models): set top_k=None in emotion pipeline to prevent index error` |
| `docs` | README, SYSTEM.md, API.md, comments | `docs(git): add workflow.md with branch and commit rules` |
| `test` | Unit/integration tests | `test(agents): add safety_gate regex layer tests` |
| `refactor` | Rewriting without changing behaviour | `refactor(orchestrator): switch to asyncio.gather for parallel inference` |
| `chore` | Config, deps, tooling, env | `chore(deps): add chromadb and sentence-transformers to requirements.txt` |
| `security` | Privacy, auth, anonymization | `security(core): add PII stripping regex + NER in anonymizer.py` |

### Scopes (project-specific)

```
core, agents, models, rag, memory, routers, frontend, tests, docs, config, deps
```

### Full Examples

```bash
# Good — tells the story
git commit -m "feat(agents): implement response_validator with forbidden pattern matcher

Adds hallucination guardrails per lecturer feedback. Blocks diagnostic
claims, medication advice, and absolute certainty phrases. Returns
validation report before assembler stage."

# Bad — useless
git commit -m "update"

# Bad — vague
git commit -m "fix stuff"
```

---

## 3. Daily Workflow (Step-by-Step)

### Starting a New Day / New Feature

```bash
# 1. Make sure dev is fresh
git checkout dev
git pull origin dev          # if you have remote, or just ensure clean

# 2. Create feature branch
git checkout -b feat/phase3-session-memory

# 3. Work. Commit often. Each commit = one logical step.
#    If you break something, you can bisect/revert cleanly.
```

### Commit Rhythm (Learning Mode)

Because you are learning, commit **more frequently** than a senior engineer. Think of commits as "save points" in a video game.

```bash
# After every working file:
git add backend/app/core/session_memory.py
git commit -m "feat(memory): add rolling session summary with ConversationBufferWindow

Implements 10-turn buffer and MongoDB persistence. Uses extractive
summarization to keep token count low."

# After fixing a bug you discovered while testing:
git add backend/app/models/loader.py
git commit -m "fix(models): add top_k=None to emotion pipeline call

Prevents RuntimeError when model returns multi-label probabilities.
Matches HF transformers v4.51.3 API."
```

### Before Ending a Session

```bash
# 1. Run tests (even if only the ones you wrote)
pytest tests/unit/core/ -v

# 2. Check what you changed
git status
git diff

# 3. Commit anything unstaged

# 4. Push branch (if remote exists)
git push origin feat/phase3-session-memory

# 5. Merge into dev ONLY when the feature works end-to-end
git checkout dev
git merge feat/phase3-session-memory --no-ff

# 6. Delete the feature branch (keeps repo clean)
git branch -d feat/phase3-session-memory
```

---

## 4. Merge Discipline

### Feature → Dev

```bash
git checkout dev
git merge feat/name --no-ff -m "merge(feat): integrate session memory system

Closes phase 3 memory foundation. Adds session_memory.py,
longitudinal_memory.py, people_graph.py with full test coverage."
```

Use `--no-ff` (no fast-forward) so the merge commit preserves the feature branch history as a bubble. This makes rollback easier.

### Dev → Main (Release)

```bash
# Only when you have a working milestone
git checkout main
git merge dev --no-ff -m "release: v0.3.0-alpha phase 3 agents complete

Includes: empathy, mindfulness, challenge, crisis agents;
RAG retriever; session + longitudinal memory; safety gate v2."

# Tag it for the viva
git tag -a v0.3.0-alpha -m "Phase 3 backend complete — ready for frontend integration"
git push origin main --tags
```

---

## 5. Tagging Strategy for Viva

Tags prove to examiners that you hit milestones. Use **semantic versioning** with phase labels.

| Tag | Meaning | When |
|-----|---------|------|
| `v0.1.0` | Foundation + Models | Already passed |
| `v0.2.0` | Phase 2 models complete | Already passed |
| `v0.3.0-alpha` | Phase 3 backend WIP | June 15 target |
| `v0.3.0` | Phase 3 backend complete | June 30 target |
| `v0.4.0-alpha` | Frontend + integration | July 15 target |
| `v0.4.0` | Full system deployed | July 25 target |
| `v1.0.0` | Viva-ready with evaluation | August 5 target |

---

## 6. Undo / Recovery Commands

You will make mistakes. These are your safety nets.

```bash
# Undo last commit but keep changes in your working directory
git reset --soft HEAD~1

# Undo last commit and DESTROY changes (careful!)
git reset --hard HEAD~1

# See what you changed in the last 3 commits
git diff HEAD~3..HEAD

# Temporarily save unfinished work and switch branches
git stash push -m "wip: halfway through anonymizer regex"
git stash pop        # restore later

# Fix the LAST commit message (only if not pushed)
git commit --amend -m "feat(agents): correct empathy_agent tone mapping"
```

---

## 7. File Exclusions (.gitignore)

Ensure your `.gitignore` at repo root contains:

```gitignore
# Environments
.venv/
venv/
__pycache__/
*.pyc
.env
.env.local

# Models (downloaded at runtime, not versioned)
backend/models/cache/
*.bin
*.safetensors

# Data
data/raw/
data/processed/*.csv
*.sqlite3

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/settings.json
.idea/
```

**Rule:** Never commit secrets, never commit model weights, never commit datasets.

---

## 8. Pre-Commit Checklist (Before Every Commit)

```
□ File has a module docstring explaining WHAT and WHY
□ Functions have type hints (def predict(text: str) -> dict:)
□ No hardcoded secrets (API keys, passwords)
□ No print() statements — use logger from utils/logger.py
□ Tests pass (at minimum: pytest tests/unit/<scope>/)
□ Git status shows only intended files
□ Commit message follows conventional format
```

---

## 9. Solo Developer Hacks

### Simulating Code Review

Since you work alone, use `git diff dev` before merging to simulate a review:

```bash
git diff dev..feat/phase3-rag
# Read every line. Ask: "Would my lecturer understand this?"
```

### Keeping a Dev Diary

Create `docs/DEVLOG.md` and append to it daily. This becomes gold for your dissertation.

```markdown
## 2026-06-06
- Fixed loader.py top_k bug (see commit 4a3b2c1)
- Learned: asyncio.gather runs coroutines concurrently, not sequentially
- Blocker: ChromaDB embedding dimension mismatch — resolved by pinning all-MiniLM-L6-v2
```

---

*Generated: 2026-06-06 | MindLens Project*
