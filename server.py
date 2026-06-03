"""
OWL Agent — Web server
Serves the HTML chat UI and handles API requests.
"""
import hashlib as _hashlib
import json
import os
import sys
import time as _time
from functools import wraps
from pathlib import Path
from threading import Lock as _Lock

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

# ── Config ───────────────────────────────────────────────────────────────────
from config import (
    PROVIDERS,
    PROVIDER_CONFIG_PATH,
    SERVER_DIR,
    SERVER_HOST,
    SERVER_PORT,
    RATE_LIMIT_PER_MINUTE,
    CORS_ORIGINS,
    load_provider_config,
    save_provider_config,
)

sys.path.insert(0, str(SERVER_DIR))

# ── App ──────────────────────────────────────────────────────────────────────
_server_start_time = _time.time()

app = Flask(__name__, static_folder=str(Path("static").resolve()))


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE, PUT, PATCH"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    resp.headers["Access-Control-Max-Age"] = "86400"
    return resp


@app.route("/api/<path:_>", methods=["OPTIONS"])
def _api_options(_):
    return "", 204


# ── Rate Limiting & Auth ─────────────────────────────────────────────────────
from middleware import rate_limit, require_auth, set_rate_limit, add_api_key, create_api_key


# ── Agent singleton ──────────────────────────────────────────────────────────
from agent.core import Agent
from agent.memory import MemorySystem
from agent.flow_engine import FlowEngine

agent = None
memory = None
flow_engine = None


def get_agent():
    global agent, memory, flow_engine
    if agent is None:
        skills_dir = Path("skills")
        print(f"[server] SERVER_DIR: {SERVER_DIR}")
        print(f"[server] skills_dir: {skills_dir} (exists: {skills_dir.exists()})")
        memory = MemorySystem(skills_dir=skills_dir if skills_dir.exists() else None)
        cfg = load_provider_config()
        if cfg.get("provider") and cfg.get("url"):
            print(f"[server] Restoring provider: {cfg['provider']} @ {cfg['url']}")
            agent = Agent(
                base_url=cfg["url"],
                api_key=cfg.get("api_key", PROVIDERS.get(cfg["provider"], {}).get("default_key", "lm-studio")),
                provider=cfg["provider"],
                model=cfg.get("model") or None,
                memory=memory,
            )
        else:
            agent = Agent(memory=memory)
    if flow_engine is None:
        flow_engine = FlowEngine()
    return agent, memory, flow_engine


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# Register blueprints
from routes import register_routes
register_routes(app)

# Import handle_command for use in chat routes
from routes.system import handle_command  # noqa: F401, E402

# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OWL Agent Server")
    parser.add_argument("--host", default=SERVER_HOST)
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--provider", default="lmstudio", choices=list(PROVIDERS.keys()))
    parser.add_argument("--lm-url", default=None)
    parser.add_argument("--lm-key", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--rate-limit", type=int, default=RATE_LIMIT_PER_MINUTE)
    args = parser.parse_args()

    provider_info = PROVIDERS[args.provider]
    base_url = args.lm_url or provider_info["default_url"]
    api_key = args.lm_key or provider_info["default_key"]

    # Rate limiting
    if args.rate_limit > 0:
        set_rate_limit(args.rate_limit)
        print(f"Rate limit: {args.rate_limit} req/min per IP")
    else:
        set_rate_limit(999999)
        print("Rate limit: disabled")

    # API key
    if args.api_key:
        add_api_key(args.api_key)
        print(f"API key auth: enabled (key: {args.api_key[:8]}...)")
    else:
        generated = create_api_key("auto")
        print(f"API key auth: auto-generated key: {generated}")

    save_provider_config(args.provider, base_url, api_key)

    print(f"Starting server on {args.host}:{args.port}")
    print(f"Provider: {args.provider} ({provider_info['label']})")
    print(f"URL: {base_url}")
    print(f"Health: http://localhost:{args.port}/api/health")
    print(f"Open http://localhost:{args.port} in your browser")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)
