import os
from flask import Flask


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    default_db = os.environ.get("KAVACH_DATABASE") or os.path.join(app.instance_path, "kavach.sqlite")
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=default_db,
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,
    )

    if test_config:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Ensure workspace and out directories exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(base_dir, "data", "workspace"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "data", "out"), exist_ok=True)

    # Unless KAVACH_KEEP_DB=1 is set or running in a test, start with an empty database
    keep_db = os.environ.get("KAVACH_KEEP_DB") == "1"
    is_testing = app.config.get("TESTING", False)
    if not keep_db and not is_testing:
        db_path = app.config["DATABASE"]
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass
        legacy_db = os.path.join(app.instance_path, "kavach.db")
        if os.path.exists(legacy_db):
            try:
                os.remove(legacy_db)
            except OSError:
                pass

    from . import db
    db.init_app(app)

    from app.config import ENABLED_PAGES
    app.config["ENABLED_PAGES"] = ENABLED_PAGES

    @app.context_processor
    def inject_globals():
        return {"enabled_pages": app.config.get("ENABLED_PAGES", ENABLED_PAGES)}

    if not is_testing:
        with app.app_context():
            db.init_db(app.config["DATABASE"])

    from . import routes
    app.register_blueprint(routes.bp)

    @app.errorhandler(413)
    def request_too_large(e):
        from flask import jsonify
        return jsonify({"error": "Uploaded payload exceeds the maximum allowed limit of 10 MB."}), 413

    @app.errorhandler(500)
    def internal_error(e):
        import logging
        from flask import jsonify
        logging.getLogger(__name__).exception("Internal server error: %s", e)
        return jsonify({"error": "An internal server error occurred. Please check server logs."}), 500

    return app
