"""MindLens agent runtime.

Modules inside this package are imported directly (`app.agents.hosted_graph`,
`app.agents.groq_client`, and so on). The package deliberately re-exports
nothing: an eager `__init__` used to import every V1 agent, so importing one
helper built the whole legacy registry.
"""

from __future__ import annotations
