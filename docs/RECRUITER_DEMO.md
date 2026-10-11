# Recruiter Demo Guide

This guide is for reviewing MindLens when cloud services are unavailable, credentials are private, or the live demo is sleeping.

## Five-minute walkthrough

1. Start with the architecture diagram in the root README.
2. Open [`backend/app/agents/hosted_graph.py`](../backend/app/agents/hosted_graph.py).
3. Identify the `StateGraph`, node names, conditional edges, and `_result_contract`.
4. Open [`backend/app/observability.py`](../backend/app/observability.py) and verify that tracing receives metadata rather than prompts or outputs.
5. Run the V2 tests:

   ```powershell
   python -m pytest backend/tests/unit/agents/test_hosted_graph.py -q
   ```

6. Review the frontend pipeline panel, which exposes actual graph progress rather than a decorative loading animation.

## What the tests demonstrate

| Scenario | Expected behavior |
|---|---|
| Explicit crisis phrase | Exits before Groq and Pinecone |
| Safe ordinary turn | Uses assessment plus one specialist |
| Model-detected crisis | Stops before specialist generation |
| Malformed Groq JSON | Uses neutral fallback and marks degradation |
| High-distress complex turn | Uses exactly three Groq calls including reviewer |

## Suggested live demo script

Use synthetic text only:

1. “I feel anxious about a presentation tomorrow.”
   - Shows assessment, retrieval, specialist route, and response.
2. “I keep putting off my evening routine.”
   - Shows a different specialist route.
3. “Everything feels overwhelming today.”
   - Can show the optional review path.
4. “I want to kill myself tonight.”
   - Demonstrates the deterministic crisis exit and controlled resources.

Do not enter real personal health information into a portfolio demo.

## What to point out in an interview

- Why safety is a graph branch before generation.
- Why the system uses one specialist instead of parallel uncontrolled agents.
- Why the reviewer is conditional and capped.
- Why user conversation is not placed in Pinecone.
- Why Langfuse receives metadata only.
- How the UI preserves existing WebSocket contracts while the backend pipeline changes.
- How degraded states make provider failures visible.
- How hosted services make Render deployment feasible on a small budget.

## If the live demo is offline

Show the README diagrams, run the mocked graph tests, inspect the graph source, and open the API contract. The architecture does not depend on a successful network call to be evaluated.

## Honest limitations

- Free-tier Render services may sleep.
- Hosted provider quotas affect latency and availability.
- The emotion fields are conversational signals, not clinical measurements.
- The remaining legacy V1 tests expect local Chroma/model behavior and are being migrated to V2 contracts.
- Production deployment still requires provider credentials and MongoDB Atlas migration.
