# init_db.py
from app import app, db, Student, Project, Assignment, Rating
from datetime import datetime
import random

# 利用应用上下文创建数据库并填充初始数据
with app.app_context():
    # 重置数据库: 删除旧表后创建新表
    db.drop_all()
    db.create_all()

    # 创建20个学生的初始数据
    students = []
    for i in range(1, 21):
        student = Student(id=i, name=f"Student{i}")
        db.session.add(student)
        students.append(student)
    db.session.flush()  # 刷新使学生ID生效

    # 为每个学生创建作品记录(初始为未提交状态)
    for student in students:
        project = Project(student_id=student.id, submitted=False, submitted_at=None)
        db.session.add(project)
    db.session.flush()

    # 随机生成学生互评任务分配: 每个学生评3个不同的他人作品
    student_ids = [s.id for s in students]
    random.shuffle(student_ids)  # 打乱学生ID顺序以随机分配
    N = len(student_ids)
    # 采用循环移位法: 每个学生评价下一个、下下个、下下下个学生的作品 (形成每人3个任务)
    for k in range(1, 4):
        for j in range(N):
            reviewer_id = student_ids[j]
            target_id = student_ids[(j + k) % N]
            if reviewer_id == target_id:
                continue  # 理论上不会发生，因为k < N且无自评
            assignment = Assignment(reviewer_id=reviewer_id, target_id=target_id)
            db.session.add(assignment)

    db.session.commit()

    # 输出验证信息：每个学生的分配情况（在控制台打印）
    for student in students:
        out_count = Assignment.query.filter_by(reviewer_id=student.id).count()
        in_count = Assignment.query.filter_by(target_id=student.id).count()
        print(f"Student {student.id}: reviews given = {out_count}, reviews received = {in_count}")
        # 预期每个学生 reviews given = 3, reviews received = 3
