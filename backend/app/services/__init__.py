"""Application services: side effects that are not graph nodes.

The V2 chat graph produces a reply. Everything that happens *around* that
reply — extracting durable memory, scheduling a follow-up check-in, and
building the progress insight — lives here as plain functions, so the graph
stays bounded and these can be tested without an agent registry.
"""
