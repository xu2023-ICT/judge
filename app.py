# app.py
from collections import defaultdict
from itertools import combinations
import random
from flask import Flask, request, jsonify, Response, session
import os, shutil, zipfile, io, csv
from datetime import datetime, timedelta
from models import db, Student, Project, GroupAssignment, Rating
from functools import wraps

app = Flask(__name__)
app.secret_key = "REPLACE_WITH_RANDOM_SECRET_STRING"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SUBMISSION_DEADLINE'] = datetime(2025, 5, 25, 23, 59, 59)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 
app.secret_key = 'CHANGE_ME_TO_A_RANDOM_SECURE_STRING'
app.permanent_session_lifetime = timedelta(hours=6)  # 设置session过期时间为6小时

db.init_app(app)  # 将数据库绑定到Flask应用

# 确保静态目录存在，用于部署作品网页
os.makedirs(os.path.join(app.root_path, "static", "static_pages"), exist_ok=True)

# 登录装饰校验器
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "User not logged in"}), 401
        return func(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['POST'])
def login():
    stu_id = (
        request.form.get('student_id') or
        (request.get_json() or {}).get('student_id')
    )
    if not stu_id:
        return jsonify({"error": "student_id is required"}), 400
    
    student = Student.query.get(stu_id)
    if not student:
        return jsonify({"error": "Student not found"}), 401
    
    session.permanent = True
    session['user_id'] = stu_id
    # 这里我不知道怎么判断是老师还是学生
    session['role'] = 'student'
    # session['role'] = 'teacher'
    return jsonify({"message": "Login successful", "student_id": stu_id}), 200

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()  # 服务器端 session 清空
    resp = jsonify({"message": "Logout successful"})
    resp.delete_cookie(
        app.config.get("SESSION_COOKIE_NAME", "session"),
        path="/",
        httponly=True,
        samesite="Lax",
    )
    return resp, 200

# @app.route('/login/test', methods=['GET'])
# @login_required
# def get_my_info():
#     student_id = session['user_id']
#     student = Student.query.get(student_id)
#     return jsonify({
#         "student_id": student.id,
#         "name": student.name,
#         "class_id": student.class_id,
#         "group": student.group
#     }), 200


# 1. 作品提交接口
@app.route('/submit', methods=['POST'])
@login_required
def submit_work():
    # ---------- 0) 截止日期检查 ----------
    if datetime.now() > app.config['SUBMISSION_DEADLINE']:
        return jsonify({"error": "Submission deadline has passed"}), 400
    
    # ---------- 1) 基本校验 ----------
    file = request.files.get('file')
    if file is None or file.filename == '':
        return jsonify({"error": "No file provided or filename is None"}), 400
    
    if not file.filename.lower().endswith('.zip'):
        return jsonify({"error": "File must be a zip archive"}), 400
    
    student_id = session['user_id']
    student = Student.query.get(student_id)
    class_id = student.class_id
    group = student.group

    # 验证学生是否存在
    student = Student.query.get(student_id)
    if not student:
        print("student not found")
        return jsonify({"error": "Student_id not found"}), 404

    # ---------- 2) 保存 zip到/uoload ----------
    upload_dir = os.path.join(app.root_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    zip_path = os.path.join(upload_dir, f"{student_id}.zip")
    file.save(zip_path)

    # ---------- 3) 解压前安全与完整性检查 ----------
    dest_dir = os.path.join(app.root_path, 'static', 'static_pages', f"class_{class_id}", f"group_{group}", str(student_id))
    # 如果该学生已有提交，先删除旧文件（覆盖提交）
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            if member.startswith('/') or '..' in member:
                continue  # 防止路径穿越
            zip_ref.extract(member, dest_dir)

    # 检查解压后是否有html css js文件
    required_suffix = {'.html': False,'.css': False,'.js': False
    }

    for root, dirs, files in os.walk(dest_dir):
        for file in files:
            if file.endswith('.html'):
                required_suffix['.html'] = True
            elif file.endswith('.css'):
                required_suffix['.css'] = True
            elif file.endswith('.js'):
                required_suffix['.js'] = True
    
    if not all(required_suffix.values()):
        shutil.rmtree(dest_dir)
        return jsonify({
            "error": "Missing required file types",
            "detail": {k: v for k, v in required_suffix.items()}
        }), 400

    # ---------- 4) 保存并更新作品 ----------
    project = Project.query.get(student_id)
    if not project:
        project = Project(student_id=student_id, submitted=True, submitted_at=datetime.now())
        db.session.add(project)
    else:
        project.submitted = True
        project.submitted_at = datetime.now()
    db.session.commit()

    # 返回提交成功消息
    return jsonify({"message": "Submission successful", "student_id": str(student_id)}), 200


# 2. 作品展示接口
@app.route('/submit/history', methods=['GET'])
@login_required
def show_work():
    student_id = session['user_id']
    student = Student.query.get(student_id)
    project = Project.query.get(student_id)
    group = student.group
    class_id = student.class_id
    if not project or not project.submitted:
        return jsonify({
            "student_id": student_id,
            "status": "未提交",
        }), 200

    # 获取请求的主机URL前缀，构建完整预览链接
    base_url = request.host_url.rstrip('/')
    link = f"{base_url}/static/static_pages/class_{class_id}/group_{group}/{student.id}/index.html"
    
    # 返回JSON对象
    return jsonify({
        "student_id": student_id,
        "status": "已提交",
        "preview_url": link
    }), 200


# 展示所有已提交作品的列表
@app.route('/works', methods=['GET'])
@login_required
def list_works():
    # 查询所有已提交作品的列表
    projects = Project.query.filter_by(submitted=True).all()
    result = []
    # 获取请求的主机URL前缀，构建完整预览链接
    base_url = request.host_url.rstrip('/')  # 去除结尾的/
    for project in projects:
        student = project.student
        group = student.group
        class_id = student.class_id
        link = f"{base_url}/static/static_pages/class_{class_id}/group_{group}/{student.id}/index.html"
        result.append({
            "student_id": student.id,
            "name": student.name,
            "preview_url": link
        })
    # 返回JSON数组
    return jsonify(result), 200

def sample_targets_for(student, target_group, k=4):
    # 1) 目标组已提交的作品
    target_group_project = (
        Student.query.join(Project, Project.student_id == Student.id).filter(
            Student.class_id == student.class_id,
            Student.group == target_group,
            Project.submitted == True
            ).all()
        )
    # 2) 如果不足 k，就到“其它组”里补齐
    if len(target_group_project) < k:
        need = k - len(target_group_project)
        pool = (
            Student.query.join(Project, Project.student_id == Student.id).filter(
                Student.class_id == student.class_id,
                Project.submitted == True,
                Student.group.notin_([student.group, target_group])
        ).all()
        )
        if pool:
            if len(pool) >= need:
                fillers = random.sample(pool, need)
            else:
                fillers = random.choices(pool, k=need)
            target_group_project.extend(fillers)
    return target_group_project

# 获取当前登录用户要评分的目标组成员列表
@app.route('/target', methods=['GET'])
@login_required
def get_target():
    student = Student.query.get(session['user_id'])

    # 1. 获取目标组
    group_assignment = GroupAssignment.query.filter_by(class_id=student.class_id, reviewer_group=student.group).first()
    if not group_assignment:
        return jsonify({"error": "No group assignment found"}), 404
    
    # 2. 获取目标组成员列表
    target_students = sample_targets_for(student, group_assignment.target_group)

    # 3. 返回作品链接
    base = request.host_url.rstrip('/')
    out = []
    for target_student in target_students:
        project = Project.query.get(target_student.id)
        submitted = project.submitted
        if not submitted:
            link = ''
        else:
            link = f"{base}/static/static_pages/class_{student.class_id}/group_{target_student.group}/{target_student.id}/index.html"
        out.append({
            "student_id": target_student.id,
            "preview_url": link
        })
    return jsonify(out), 200



# 评分函数
grade_map = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1}
second_round_open = False
def rate_round(round_num):
    global second_round_open
    if round_num == 2 and not second_round_open:
        return jsonify({"error": "Second round not open yet"}), 400
    
    stu_id = session.get('user_id')
    if not stu_id:
        return jsonify({"error": "User not logged in"}), 401
    student = Student.query.get(stu_id)
    
    # 这里我不知道怎么判断学生还是老师
    # stu_role = session.get('role')
    # if stu_role != 'student':
    #     return jsonify({"error": "User not a student"}), 401

    # ------ 1) 获取要评分的目标组 ------
    groupassignment = GroupAssignment.query.filter_by(
        class_id = student.class_id, reviewer_group = student.group
    ).first()
    if not groupassignment:
        return jsonify({"error": "no assignmet"}), 404
    
    # ------ 2) 获取目标组成员 不够则补齐四份 ------
    target_students = sample_targets_for(student, groupassignment.target_group)
    
    # ------ 3) 解析json数据 ------
    ratings_map = request.get_json(silent=True)
    if ratings_map is None or not isinstance(ratings_map, dict):
        return jsonify({"error": "data is None or is not dict"}), 400
    
    # ------ 4) 重复提交 以及判断提交是否足够 ------
    if Rating.query.filter_by(
        reviewer_id = stu_id, round = round_num
    ).first():
        return jsonify({"error": "repeat submmit"}), 400
    
    for target_student in target_students:
        target_student_id = str(target_student.id)
        if target_student_id not in ratings_map:
            return jsonify({"error": f"Missing rating for student {target_student_id}"}), 400
    
    # ------ 5) 评分 ------
    for target_student in target_students:
        target_student_id = str(target_student.id)
        project = Project.query.get(target_student_id)
        if project and project.submitted:
            innovation_score = ratings_map[target_student_id].get('innovation')
            professional_score = ratings_map[target_student_id].get('professional')
            if innovation_score not in grade_map or professional_score not in grade_map:
                return jsonify({"error": f"{target_student_id} rate must from A-E"}), 400
            I, P = grade_map[innovation_score], grade_map[professional_score]
        else:
            I, P = 0, 0

        
        db.session.add(Rating(
            reviewer_id = stu_id,
            reviewer_class = student.class_id,
            reviewer_group = student.group,
            target_group = groupassignment.target_group,
            target_id = target_student.id,
            innovation_score = I,
            professional_score = P,
            round = round_num
        ))
    db.session.commit()
    return jsonify({"message": "sucessful rate"}), 200

@app.route('/rate/first', methods=['POST'])
@login_required
def rate_first():
    return rate_round(1)

@app.route('/rate/second', methods=['POST'])
@login_required
def rate_second():
    return rate_round(2)


# 杜师姐定义的公式
def total_score(P: int, I: int) -> float:
    return (1 - (P - 1) / 4) * P + ((P - 1) / 4) * I

@app.route('/analysis', methods=['GET'])
@login_required
def analysis():
    # 当前同学所在的班级和小组
    student = Student.query.get(session['user_id'])
    class_id = student.class_id
    group_id = student.group

    # 1. 拉出这一组里，所有第一轮评分记录
    ratings = Rating.query.filter_by(
        reviewer_class=class_id,
        reviewer_group=group_id,
        round=1
    ).all()

    # 2. 找到组内所有评审人（学号）和所有被评作品ID
    reviewer_ids = sorted({r.reviewer_id for r in ratings})
    target_ids   = sorted({r.target_id   for r in ratings})

    # 3. 聚合到一个 dict：id_grade[reviewer_id][target_id] = 总分
    id_grade = defaultdict(dict)
    for r in ratings:
        T = total_score(r.professional_score, r.innovation_score)
        id_grade[r.reviewer_id][r.target_id] = T

    # 4. 准备所有两两作品对
    pairs = list(combinations(target_ids, 2))

    # 5. 构造表格数据：每一行一个 (i,j)，列名就是各个 reviewer_id
    table_data = []
    for i, j in pairs:
        row = {"pair": (i, j)}
        for rid in reviewer_ids:
            Ti = id_grade[rid].get(i, 0)
            Tj = id_grade[rid].get(j, 0)
            if Ti > Tj:
                comp = f"{i}>{j}"
            elif Tj > Ti:
                comp = f"{j}>{i}"
            else:
                comp = f"{i}={j}"
            row[str(rid)] = comp
        table_data.append(row)

    # 6. 返回 JSON，前端直接用 keys 渲染表头
    return jsonify({
        "reviewers": reviewer_ids,  # 前端可以读这个数组来做 <th>，也可直接从每行 keys 里取
        "data":      table_data
    })

        
# 仅在直接运行app.py时启动Flask开发服务器
if __name__ == '__main__':
    app.run(debug=True)
