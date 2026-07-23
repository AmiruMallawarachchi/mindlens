# MindLens Backend API

The backend exposes REST endpoints under `/api/v1` and chat over WebSocket.

## Authentication

`POST /api/v1/auth/register` and `POST /api/v1/auth/login` set an httpOnly
`access_token`, an httpOnly `refresh_token`, and a readable `csrf_token` cookie.
The response also returns the access and CSRF tokens for clients that use bearer
authentication.

Production browser requests must use `credentials: "include"`. State-changing
cookie-authenticated requests must send the returned CSRF token as
`X-CSRF-Token`. Bearer-authenticated requests do not require CSRF validation.

The refresh token is rotated by `POST /api/v1/auth/refresh`. Logout is handled by
`POST /api/v1/auth/logout`.

## Main routes

- `GET /health`: process liveness; does not touch dependencies.
- `GET /ready`: MongoDB and configured model readiness.
- `POST /api/v1/sessions`: create a conversation session.
- `GET /api/v1/sessions`: list the authenticated user's sessions.
- `GET /api/v1/sessions/{session_id}`: get one owned session.
- `DELETE /api/v1/sessions/{session_id}`: end one owned session.
- `GET /api/v1/onboarding/status`: onboarding state.
- `POST /api/v1/onboarding/step/{step_number}`: save one onboarding step.
- `GET /api/v1/memory`: get the authenticated user's memory.
- `GET /api/v1/dashboard/summary`: dashboard summary.
- `GET /api/v1/admin/system`: admin-only dependency and model status.
- `GET /api/v1/admin/models`: admin-only model registry status.

## WebSocket chat

Connect to `wss://<api-host>/ws/chat/{session_id}`. Browser clients should use
the access cookie. A client that cannot use cookies may offer the protocol
`mindlens.jwt.<access-token>`; the server echoes the selected protocol. Tokens
are never accepted in URL query parameters.

```json
{"type": "message", "text": "I have been feeling anxious today."}
```

The server emits `thinking_update`, `stream_chunk`, `response`, `crisis_response`,
and `error` messages. Crisis responses bypass RAG and generative agents.
