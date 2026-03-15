from __future__ import annotations

from aiohttp import web

from control_plane.prompt_execution_gateway import create_app


def main():
    web.run_app(create_app(), host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()