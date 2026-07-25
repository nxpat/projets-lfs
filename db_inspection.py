from project import create_app, db
# Import the models involved in the traceback
from project.models import SchoolYear, Personnel, User

app = create_app()

with app.app_context():
    print("--- 1. Testing SchoolYear rows ---")
    for sy in SchoolYear.query.yield_per(1):
        try:
            # Force SQLAlchemy to load all attributes on this instance
            db.session.refresh(sy)
        except Exception as e:
            print(f"❌ Corrupted JSON in SchoolYear ID: {getattr(sy, 'id', 'N/A')} | Error: {e}")

    print("\n--- 2. Testing User rows ---")
    for u in User.query.yield_per(1):
        try:
            db.session.refresh(u)
        except Exception as e:
            print(f"❌ Corrupted JSON in User ID: {u.id} | Email: {u.email} | Error: {e}")

    print("\n--- 3. Testing Personnel rows ---")
    for p in Personnel.query.yield_per(1):
        try:
            db.session.refresh(p)
        except Exception as e:
            print(f"❌ Corrupted JSON in Personnel ID: {p.id} | Error: {e}")

    print("\nScan complete.")
