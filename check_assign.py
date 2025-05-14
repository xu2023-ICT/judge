from app import app, db
from models import Assignment

with app.app_context():
    assigns = Assignment.query.filter_by(reviewer_id=1).all()
    print("Student 1 is assigned to review:")
    for a in assigns:
        print(f"- Student {a.target_id}")
