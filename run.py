from dotenv import load_dotenv
load_dotenv()

import os
from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create all database tables. Run: flask init-db"""
    with app.app_context():
        db.create_all()
    print("Database tables created.")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")