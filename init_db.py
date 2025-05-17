from flask import Flask
from models import db, Student, Project, GroupAssignment, Rating
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.drop_all()
    db.create_all()

    df = pd.read_excel('grouped_result.xlsx')

    for _, row in df.iterrows():
        student = Student(
            id=str(row['id']),
            name= str(row['姓名']),
            group= int(row['group_id']),
            class_id = int(row['class']),
        )
        project = Project(student_id=student.id, submitted=False)

        db.session.add(student)
        db.session.add(project)

    seen = set()
    for _, row in df.iterrows():
        class_id = int(row['class'])
        reviewer_group = int(row['group_id'])
        target_group = int(row['assign_work'])

        key = (class_id, reviewer_group, target_group)
        if key in seen:
            continue
        seen.add(key)

        groupassignment = GroupAssignment(
            class_id=class_id,
            reviewer_group=reviewer_group,
            target_group=target_group
        )
        db.session.add(groupassignment)
    
    db.session.commit()
    print("Database initialized and populated with data from grouped_result.csv")



