"""
Flask application factory for biosimdb-interface.

Creates and configures the Flask app, registers blueprints,
and loads environment variables for Invenio OAuth integration.
"""

import os

__version__ = "0.0.1"

from dotenv import load_dotenv
from flask import Flask

load_dotenv()
# UPLOAD_FOLDER = "/tmp"


def create_app(test_config=None):
    """Create and configure the Flask application.

    Args:
        test_config: Optional mapping to override config for testing.

    Returns:
        Configured Flask app instance.
    """
    # create and configure the app
    APPLICATION_BASE = os.getenv("APPLICATION_BASE", "")
    app = Flask(
        __name__,  # name of the current Python module
        template_folder="templates",  # where html files are stored.
        static_folder="static",  # used for css and js files.
        static_url_path=f"{APPLICATION_BASE}/static",
        instance_relative_config=True,
    )  # create flask instance

    app.config["APPLICATION_BASE"] = os.getenv("APPLICATION_BASE", "")

    # check secret key is not "dev" for prod
    secret_key = os.getenv("SECRET_KEY", "dev")
    if secret_key == "dev" and not app.debug:
        raise RuntimeError("SECRET_KEY must be set to a secure value in production.")
    app.config["SECRET_KEY"] = secret_key

    # App and Invenio OAuth2 configuration — values loaded from .env
    app.config.from_mapping(
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "/tmp"),  # App specific
        CLIENT_ID=os.getenv("CLIENT_ID", ""),
        CLIENT_SECRET=os.getenv("CLIENT_SECRET", ""),
        AUTH_URL=os.getenv("AUTH_URL", ""),
        TOKEN_URL=os.getenv("TOKEN_URL", ""),
        BASE_URL=os.getenv("BASE_URL", ""),
        API_BASE=os.getenv("API_BASE", ""),
        REDIRECT_URI=os.getenv("REDIRECT_URI", ""),
        SCOPES=os.getenv("SCOPES", "").strip(),
    )  # invenio app configs

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    @app.context_processor
    def inject_base_url():
        return {
            "BASE_URL": app.config.get("BASE_URL", ""),
            "APPLICATION_BASE": app.config.get("APPLICATION_BASE", ""),
        }

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from .form import form_bp

    app.register_blueprint(form_bp, url_prefix=app.config["APPLICATION_BASE"])

    from .login import bp as login_bp

    app.register_blueprint(login_bp, url_prefix=app.config["APPLICATION_BASE"])

    return app
