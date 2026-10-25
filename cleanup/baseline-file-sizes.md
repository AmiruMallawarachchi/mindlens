# Baseline source file sizes

Read-only line-count inventory of every Python file under `backend/` and every TypeScript/TSX file under `frontend/src/`.

Files counted: **215**
Files over 300 lines: **43** (flagged in the table)

Line counts use `splitlines()` on the current file contents. Generated dependencies and build outputs are outside these source roots.

| Lines | File | Flag |
|---:|---|---|
| 1463 | `frontend/src/components/ai-elements/prompt-input.tsx` | **OVER 300** |
| 820 | `frontend/src/components/home/home-page.tsx` | **OVER 300** |
| 816 | `backend/tests/unit/agents/test_orchestrator.py` | **OVER 300** |
| 781 | `backend/app/agents/orchestrator.py` | **OVER 300** |
| 737 | `backend/app/routers/chat.py` | **OVER 300** |
| 731 | `frontend/src/lib/use-mindlens-client.ts` | **OVER 300** |
| 714 | `backend/tests/unit/routers/test_chat.py` | **OVER 300** |
| 695 | `backend/app/routers/auth.py` | **OVER 300** |
| 660 | `frontend/src/components/chat/chat-sidebar.tsx` | **OVER 300** |
| 620 | `frontend/src/components/companion/companion-avatar.tsx` | **OVER 300** |
| 562 | `frontend/src/components/ai-elements/code-block.tsx` | **OVER 300** |
| 504 | `backend/app/middleware/auth.py` | **OVER 300** |
| 461 | `backend/tests/unit/routers/test_session.py` | **OVER 300** |
| 460 | `frontend/src/lib/api.ts` | **OVER 300** |
| 437 | `backend/tests/unit/routers/test_auth.py` | **OVER 300** |
| 421 | `backend/app/routers/session.py` | **OVER 300** |
| 419 | `backend/app/models/loader.py` | **OVER 300** |
| 414 | `backend/tests/unit/models/test_loader.py` | **OVER 300** |
| 414 | `frontend/src/components/ai-elements/context.tsx` | **OVER 300** |
| 408 | `frontend/src/lib/emotion.ts` | **OVER 300** |
| 400 | `backend/tests/unit/routers/test_account.py` | **OVER 300** |
| 399 | `frontend/src/components/chat/chat-screen.tsx` | **OVER 300** |
| 395 | `backend/app/agents/groq_client.py` | **OVER 300** |
| 389 | `backend/app/routers/onboarding.py` | **OVER 300** |
| 387 | `backend/app/agents/hosted_graph.py` | **OVER 300** |
| 375 | `frontend/src/lib/types.ts` | **OVER 300** |
| 370 | `backend/app/core/emotional_os.py` | **OVER 300** |
| 368 | `frontend/src/components/pages/memory-page.tsx` | **OVER 300** |
| 365 | `backend/app/core/connection_manager.py` | **OVER 300** |
| 360 | `frontend/src/components/ai-elements/message.tsx` | **OVER 300** |
| 358 | `frontend/src/components/chat/composer.tsx` | **OVER 300** |
| 352 | `backend/app/rag/retriever.py` | **OVER 300** |
| 347 | `backend/app/routers/memory.py` | **OVER 300** |
| 342 | `backend/tests/unit/rag/test_retriever.py` | **OVER 300** |
| 341 | `frontend/src/components/chat/message-flow.tsx` | **OVER 300** |
| 339 | `frontend/src/components/pages/progress-page.tsx` | **OVER 300** |
| 335 | `frontend/src/components/admin/admin-dashboard.tsx` | **OVER 300** |
| 322 | `backend/app/agents/streaming.py` | **OVER 300** |
| 317 | `backend/tests/unit/agents/test_session_memory_save.py` | **OVER 300** |
| 316 | `frontend/src/lib/reasoning.ts` | **OVER 300** |
| 314 | `frontend/src/components/pages/journal-page.tsx` | **OVER 300** |
| 311 | `backend/app/memory/session.py` | **OVER 300** |
| 304 | `backend/tests/unit/middleware/test_auth.py` | **OVER 300** |
| 296 | `frontend/src/components/ai-elements/inline-citation.tsx` |  |
| 292 | `backend/app/rag/vector_store.py` |  |
| 288 | `backend/app/agents/session_memory_save.py` |  |
| 288 | `backend/tests/unit/routers/test_memory.py` |  |
| 287 | `backend/app/routers/account.py` |  |
| 280 | `backend/app/agents/empathy_agent.py` |  |
| 280 | `frontend/src/components/onboarding/onboarding-flow.tsx` |  |
| 277 | `backend/tests/unit/agents/test_streaming.py` |  |
| 276 | `frontend/src/components/chat/breathe-card.tsx` |  |
| 263 | `backend/app/routers/journal.py` |  |
| 261 | `frontend/src/components/settings/sections/appearance.tsx` |  |
| 257 | `frontend/src/components/ui/dropdown-menu.tsx` |  |
| 251 | `backend/app/config.py` |  |
| 248 | `frontend/src/components/settings/ui.tsx` |  |
| 241 | `frontend/src/components/ui/carousel.tsx` |  |
| 232 | `backend/tests/unit/agents/test_groq_client.py` |  |
| 230 | `backend/tests/unit/core/test_connection_manager.py` |  |
| 228 | `backend/tests/unit/routers/test_onboarding.py` |  |
| 226 | `frontend/src/components/ai-elements/reasoning.tsx` |  |
| 223 | `backend/tests/unit/agents/test_empathy_agent.py` |  |
| 222 | `backend/app/agents/response_validator.py` |  |
| 221 | `backend/tests/unit/memory/test_session.py` |  |
| 217 | `backend/app/agents/safety_gate.py` |  |
| 216 | `backend/tests/unit/routers/test_journal.py` |  |
| 215 | `backend/tests/conftest.py` |  |
| 215 | `frontend/src/components/settings/sections/privacy.tsx` |  |
| 213 | `backend/tests/unit/test_main.py` |  |
| 209 | `backend/app/agents/response_assembler.py` |  |
| 209 | `backend/tests/unit/agents/test_personality_agent.py` |  |
| 206 | `backend/app/agents/distortion_agent.py` |  |
| 206 | `backend/tests/unit/routers/test_dashboard.py` |  |
| 205 | `frontend/src/components/auth-gate.tsx` |  |
| 203 | `frontend/src/components/chat/pipeline-trace.tsx` |  |
| 201 | `backend/app/core/anonymizer.py` |  |
| 194 | `backend/tests/unit/core/test_emotional_os.py` |  |
| 191 | `backend/app/core/memory_recall.py` |  |
| 190 | `frontend/src/components/ui/select.tsx` |  |
| 186 | `frontend/src/components/settings/settings-modal.tsx` |  |
| 185 | `frontend/src/components/settings/sections/account.tsx` |  |
| 184 | `frontend/src/components/ui/command.tsx` |  |
| 183 | `frontend/src/components/chat/reasoning-trail.tsx` |  |
| 180 | `frontend/src/lib/websocket.ts` |  |
| 176 | `backend/app/agents/base_agent.py` |  |
| 174 | `backend/tests/unit/agents/test_challenge_agent.py` |  |
| 174 | `frontend/src/components/ai-elements/confirmation.tsx` |  |
| 173 | `frontend/src/components/ai-elements/tool.tsx` |  |
| 173 | `frontend/src/components/pages/page-shell.tsx` |  |
| 172 | `backend/tests/unit/core/test_memory_recall.py` |  |
| 170 | `frontend/src/components/ui/input-group.tsx` |  |
| 169 | `backend/app/routers/dashboard.py` |  |
| 169 | `frontend/src/lib/admin-api.ts` |  |
| 168 | `frontend/src/components/ai-elements/conversation.tsx` |  |
| 167 | `backend/tests/unit/agents/test_base_agent.py` |  |
| 165 | `backend/tests/unit/agents/test_response_assembler.py` |  |
| 158 | `frontend/src/components/ui/dialog.tsx` |  |
| 155 | `backend/app/rag/ingest.py` |  |
| 155 | `frontend/src/components/field/emotion-field.tsx` |  |
| 154 | `backend/app/main.py` |  |
| 153 | `backend/app/agents/personality_agent.py` |  |
| 151 | `backend/tests/unit/agents/test_safety_gate_redteam.py` |  |
| 151 | `frontend/src/components/settings/sections/general.tsx` |  |
| 149 | `backend/app/db.py` |  |
| 143 | `frontend/src/components/ai-elements/agent.tsx` |  |
| 139 | `backend/app/agents/challenge_agent.py` |  |
| 137 | `backend/tests/unit/rag/test_vector_store.py` |  |
| 132 | `backend/app/agents/journaling_agent.py` |  |
| 132 | `backend/app/agents/question_options.py` |  |
| 129 | `backend/app/agents/mindfulness_agent.py` |  |
| 121 | `backend/tests/unit/agents/test_reflection_agent.py` |  |
| 119 | `backend/tests/unit/routers/test_system.py` |  |
| 118 | `backend/app/agents/routine_agent.py` |  |
| 118 | `frontend/src/components/companion/family.tsx` |  |
| 117 | `backend/tests/unit/agents/test_groq_degradation.py` |  |
| 115 | `backend/app/agents/progress_agent.py` |  |
| 112 | `backend/app/core/emotion_labels.py` |  |
| 110 | `frontend/src/components/mindlens-app.tsx` |  |
| 109 | `frontend/src/components/ui/avatar.tsx` |  |
| 103 | `backend/app/agents/checkin_agent.py` |  |
| 102 | `backend/tests/unit/agents/test_hosted_graph.py` |  |
| 100 | `backend/tests/unit/agents/test_question_options.py` |  |
| 99 | `backend/app/agents/reflection_agent.py` |  |
| 99 | `backend/tests/unit/agents/test_safety_gate.py` |  |
| 97 | `backend/tests/unit/rag/test_ingest.py` |  |
| 96 | `frontend/src/components/settings/sections/memory.tsx` |  |
| 93 | `frontend/src/lib/preview.ts` |  |
| 92 | `frontend/src/components/ui/card.tsx` |  |
| 91 | `frontend/src/components/chat/live-stage-trail.tsx` |  |
| 91 | `frontend/src/components/ui/tabs.tsx` |  |
| 89 | `frontend/src/components/ui/popover.tsx` |  |
| 88 | `backend/tests/unit/agents/test_routine_agent.py` |  |
| 87 | `frontend/src/components/ai-elements/task.tsx` |  |
| 86 | `frontend/src/components/chat/crisis-banner.tsx` |  |
| 86 | `frontend/src/lib/companions.ts` |  |
| 84 | `frontend/src/components/chat/emotion-read.tsx` |  |
| 83 | `frontend/src/components/ui/button-group.tsx` |  |
| 83 | `frontend/src/lib/use-grade.ts` |  |
| 81 | `backend/app/agents/crisis_agent.py` |  |
| 81 | `frontend/src/components/settings/use-prefs.ts` |  |
| 80 | `backend/tests/unit/agents/test_crisis_agent.py` |  |
| 77 | `frontend/src/components/ai-elements/shimmer.tsx` |  |
| 76 | `frontend/src/lib/use-read-aloud.ts` |  |
| 73 | `backend/tests/unit/agents/test_distortion_agent.py` |  |
| 72 | `backend/app/agents/checkin_scheduler.py` |  |
| 71 | `frontend/src/components/ai-elements/checkpoint.tsx` |  |
| 69 | `backend/scripts/make_admin.py` |  |
| 69 | `backend/tests/unit/test_config.py` |  |
| 66 | `backend/app/observability.py` |  |
| 66 | `frontend/src/components/ui/accordion.tsx` |  |
| 66 | `frontend/src/components/ui/alert.tsx` |  |
| 65 | `backend/tests/unit/core/test_emotion_labels.py` |  |
| 64 | `frontend/src/components/ui/button.tsx` |  |
| 62 | `backend/tests/integration/test_full_pipeline.py` |  |
| 60 | `backend/tests/unit/core/test_anonymizer.py` |  |
| 59 | `frontend/src/components/brand/wordmark.tsx` |  |
| 58 | `backend/app/agents/__init__.py` |  |
| 58 | `frontend/src/components/ui/scroll-area.tsx` |  |
| 57 | `backend/app/rag/hosted_retriever.py` |  |
| 57 | `backend/tests/unit/agents/test_mindfulness_agent.py` |  |
| 57 | `backend/tests/unit/agents/test_response_validator.py` |  |
| 57 | `frontend/src/app/layout.tsx` |  |
| 57 | `frontend/src/components/ai-elements/suggestion.tsx` |  |
| 57 | `frontend/src/components/ui/tooltip.tsx` |  |
| 56 | `backend/tests/unit/agents/test_checkin_scheduler.py` |  |
| 54 | `frontend/src/app/companion-lab/page.tsx` |  |
| 54 | `frontend/src/app/global-error.tsx` |  |
| 50 | `backend/app/routers/system.py` |  |
| 50 | `frontend/src/components/home/magnetic.tsx` |  |
| 48 | `frontend/src/components/ui/badge.tsx` |  |
| 47 | `backend/app/utils/logger.py` |  |
| 46 | `backend/tests/unit/agents/test_journaling_agent.py` |  |
| 46 | `frontend/src/lib/personalities.ts` |  |
| 45 | `backend/tests/unit/agents/test_progress_agent.py` |  |
| 44 | `backend/tests/unit/agents/test_checkin_agent.py` |  |
| 44 | `frontend/src/components/home/reveal.tsx` |  |
| 44 | `frontend/src/components/ui/hover-card.tsx` |  |
| 43 | `frontend/src/lib/use-sidebar-collapsed.ts` |  |
| 35 | `frontend/src/components/ui/switch.tsx` |  |
| 33 | `frontend/src/components/ui/collapsible.tsx` |  |
| 32 | `frontend/src/app/error.tsx` |  |
| 31 | `frontend/src/components/ui/progress.tsx` |  |
| 30 | `frontend/src/components/settings/nav.ts` |  |
| 28 | `backend/tests/unit/utils/test_logger.py` |  |
| 28 | `frontend/src/components/ui/separator.tsx` |  |
| 26 | `backend/app/core/__init__.py` |  |
| 25 | `frontend/src/app/not-found.tsx` |  |
| 22 | `backend/app/routers/__init__.py` |  |
| 21 | `frontend/src/components/ui/input.tsx` |  |
| 18 | `backend/run.py` |  |
| 18 | `frontend/src/components/ui/textarea.tsx` |  |
| 16 | `backend/tests/unit/test_import_smoke.py` |  |
| 16 | `frontend/src/components/ui/spinner.tsx` |  |
| 13 | `frontend/src/app/app/page.tsx` |  |
| 6 | `frontend/src/lib/utils.ts` |  |
| 5 | `backend/app/middleware/__init__.py` |  |
| 5 | `backend/app/rag/__init__.py` |  |
| 5 | `frontend/src/app/admin/page.tsx` |  |
| 5 | `frontend/src/app/page.tsx` |  |
| 1 | `backend/app/models/__init__.py` |  |
| 1 | `backend/tests/unit/middleware/__init__.py` |  |
| 1 | `backend/tests/unit/rag/__init__.py` |  |
| 0 | `backend/app/__init__.py` |  |
| 0 | `backend/app/memory/__init__.py` |  |
| 0 | `backend/app/utils/__init__.py` |  |
| 0 | `backend/tests/__init__.py` |  |
| 0 | `backend/tests/integration/__init__.py` |  |
| 0 | `backend/tests/unit/__init__.py` |  |
| 0 | `backend/tests/unit/agents/__init__.py` |  |
| 0 | `backend/tests/unit/core/__init__.py` |  |
| 0 | `backend/tests/unit/models/__init__.py` |  |
| 0 | `backend/tests/unit/routers/__init__.py` |  |
| 0 | `backend/tests/unit/test_db.py` |  |
| 0 | `backend/tests/unit/utils/__init__.py` |  |
