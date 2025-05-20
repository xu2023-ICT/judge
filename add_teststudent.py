# init_groups.py

from app import app, db
from models import Student, Project, GroupAssignment

def setup_groups():
    with app.app_context():
        # —— 1. 清除旧表并重建新表 —— 
        db.drop_all()
        db.create_all()

        class_id = 1
        # 组名映射：A→0, B→1, C→2
        group_map = {'a': 0, 'b': 1, 'c': 2}
        students = [
            # (学号, 组别, 是否提交)
            ('A1', 'a', True), ('A2', 'a', True), ('A3', 'a', True), ('A4', 'a', True),
            ('B1', 'b', True), ('B2', 'b', True), ('B3', 'b', True), ('B4', 'b', False),
            ('C1', 'c', True), ('C2', 'c', True), ('C3', 'c', True),
        ]

        # —— 2. 插入学生和作品 —— 
        for sid, grp, submitted in students:
            stu = Student(
                id=sid,
                name=f"Student_{sid}",
                class_id=class_id,
                group=group_map[grp]
            )
            db.session.add(stu)
            db.session.add(Project(
                student_id=sid,
                submitted=submitted
            ))

        # —— 3. 建立互评映射 A→B, B→C, C→A —— 
        assignments = [
            (0, 1),  # A评B
            (1, 2),  # B评C
            (2, 0),  # C评A
        ]
        for reviewer_group, target_group in assignments:
            db.session.add(GroupAssignment(
                class_id=class_id,
                reviewer_group=reviewer_group,
                target_group=target_group
            ))

        db.session.commit()
        print("✅ 已完成 drop_all, create_all 并初始化三组互评数据")

if __name__ == '__main__':
    setup_groups()
