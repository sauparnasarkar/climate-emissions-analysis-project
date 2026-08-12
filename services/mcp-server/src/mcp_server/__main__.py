"""Entry point: `python -m mcp_server` (not `python -m mcp_server.server` -- see the note
at the bottom of server.py for why that form silently runs a near-empty server instead).
"""

from .server import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # anyio.run()/asyncio.run() (inside main()) already shut the server down cleanly by
        # the time this fires -- Ctrl+C during a running server is the normal way to stop it,
        # not an error, so exit quietly instead of letting the default KeyboardInterrupt
        # traceback print after a shutdown that already succeeded.
        pass
