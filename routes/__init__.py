"""
Route registration — imports all blueprints and registers them on the app.
"""
from routes.chat import chat_bp
from routes.skills import skills_bp
from routes.provider import provider_bp
from routes.memory import memory_bp
from routes.flow import flow_bp
from routes.system import system_bp, handle_command
from routes.teams import teams_bp
from routes.webhook import webhook_bp
from routes.scheduler import scheduler_bp
from routes.secrets import secrets_bp
from routes.react import react_bp


def register_routes(app):
    """Register all route blueprints on the Flask app."""
    app.register_blueprint(chat_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(provider_bp)
    app.register_blueprint(memory_bp)
    app.register_blueprint(flow_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(scheduler_bp)
    app.register_blueprint(secrets_bp)
    app.register_blueprint(react_bp)
