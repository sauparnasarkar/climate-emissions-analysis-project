"""Entry point: `python -m mcp_server` (not `python -m mcp_server.server` -- see the note
at the bottom of server.py for why that form silently runs a near-empty server instead).
"""

from .server import main

if __name__ == "__main__":
    main()
