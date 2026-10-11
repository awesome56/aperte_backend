"""ALICE for Aperte — unified AI agent (tools + orchestration + routes in one place).

Unlike the HRMS setup (PHP McpBridge + Node mcp-server + Python daemon),
Aperte's Flask backend hosts everything here:

- models.py  — conversation persistence (DB, not JSON files)
- tools.py   — tool implementations (direct SQLAlchemy, request-scoped user)
- agent.py   — DeepSeek orchestration loop (streaming, 10-step limit)
- routes.py  — Flask blueprint: /chat (SSE), /conversations, /execute, /mcp, /health
"""
