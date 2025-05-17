# app.py
from flask import Flask, request, jsonify, Response, session
import os, shutil, zipfile, io, csv
from datetime import datetime, timedelta
from models import db, Student, Project, GroupAssignment, Rating
from functools import wraps

app = Flask(__name__)
app.secret_key = "REPLACE_WITH_RANDOM_SECRET_STRING"

# 配置数据库为SQLite文件 webscore.db
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

@app.route('/login/test', methods=['GET'])
@login_required
def get_my_info():
    student_id = session['user_id']
    student = Student.query.get(student_id)
    return jsonify({
        "student_id": student.id,
        "name": student.name,
        "class_id": student.class_id,
        "group": student.group
    }), 200


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


@app.route('/submit/<int:student_id>', methods=['GET'])
def show_work(student_id):
    # 查询指定学生的作品 这里不能直接展示 因为我还不知道学生登录那个界面怎么做的
    project = Project.query.get(student_id)
    if not project or not project.submitted:
        return jsonify({
            "student_id": student_id,
            "status": "未提交",
        }), 200

    # 获取请求的主机URL前缀，构建完整预览链接
    base_url = request.host_url.rstrip('/')
    link = f"{base_url}/static/static_pages/{student_id}/index.html"
    
    # 返回JSON对象
    return jsonify({
        "student_id": student_id,
        "status": "已提交",
        "preview_url": link
    }), 200


# 2. 作品展示接口
@app.route('/works', methods=['GET'])
def list_works():
    # 查询所有已提交作品的列表
    projects = Project.query.filter_by(submitted=True).all()
    result = []
    # 获取请求的主机URL前缀，构建完整预览链接
    base_url = request.host_url.rstrip('/')  # 去除结尾的/
    for project in projects:
        student = project.student
        link = f"{base_url}/static/static_pages/{student.id}/index.html"
        result.append({
            "student_id": student.id,
            "name": student.name,
            "preview_url": link
        })
    # 返回JSON数组
    return jsonify(result), 200



# 3. 评分接口
@app.route('/rate', methods=['POST'])
def rate_work():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    reviewer_id = data.get('reviewer_id')
    target_id = data.get('target_id')
    innov_grade = data.get('innovation')
    prof_grade = data.get('professional')

    # 校验必要字段是否齐全
    if not reviewer_id or not target_id or not innov_grade or not prof_grade:
        return jsonify({"error": "reviewer_id, target_id, innovation, and professional fields are required"}), 400

    # 校验评审者和目标是否为不同学生
    if reviewer_id == target_id:
        return jsonify({"error": "Students cannot rate their own work"}), 400

    # 验证学生ID有效性
    reviewer = Student.query.get(reviewer_id)
    target_student = Student.query.get(target_id)
    if not reviewer or not target_student:
        return jsonify({"error": "Invalid reviewer_id or target_id"}), 404

    # 检查该评审者是否被分配了评价该目标作品（存在Assignment任务）
    assignment = Assignment.query.filter_by(reviewer_id=reviewer_id, target_id=target_id).first()
    if not assignment:
        # 若无对应任务，拒绝评分
        return jsonify({"error": "This rating assignment is not allowed"}), 403

    # 检查是否已经评分过（避免重复评分同一作品）
    existing = Rating.query.filter_by(reviewer_id=reviewer_id, target_id=target_id).first()
    if existing:
        return jsonify({"error": "This work is already rated by this reviewer"}), 400

    # 检查目标作品是否已提交，未提交则无法评分
    project = Project.query.get(target_id)
    if not project or not project.submitted:
        return jsonify({"error": "Target student's work not available to rate"}), 400

    # 验证评分等级是否在A-E范围
    valid_grades = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1}
    if innov_grade not in valid_grades or prof_grade not in valid_grades:
        return jsonify({"error": "Grades must be one of A, B, C, D, E"}), 400

    # 转换A-E为数值分数
    innov_score = valid_grades[innov_grade]
    prof_score = valid_grades[prof_grade]

    # 保存评分记录到数据库
    rating = Rating(reviewer_id=reviewer_id, target_id=target_id,
                    innovation_score=innov_score, professional_score=prof_score)
    db.session.add(rating)
    db.session.commit()

    return jsonify({"message": "Rating submitted successfully"}), 200

# 4. 教师分析接口 - 获取统计数据
@app.route('/analysis', methods=['GET'])
def analysis():
    projects = Project.query.filter_by(submitted=True).all()
    analysis_data = []
    score_data = {}  # 存储每个作品的分数列表等信息

    # 计算每个作品的平均分和方差
    for proj in projects:
        sid = proj.student_id
        # 获取该作品收到的所有评分记录
        ratings = Rating.query.filter_by(target_id=sid).all()
        # 计算总分列表（创新+专业）
        scores = [(r.innovation_score + r.professional_score) for r in ratings]
        if scores:
            avg_score = sum(scores) / len(scores)
            # 方差 = ∑(score - avg)^2 / n
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        else:
            avg_score = None
            variance = None
        score_data[sid] = {
            "name": proj.student.name,
            "avg": avg_score,
            "var": variance
        }

    # 根据平均分计算排名（平均分高的排名靠前）
    ranked_list = sorted(
        [(sid, data["avg"]) for sid, data in score_data.items() if data["avg"] is not None],
        key=lambda x: x[1], reverse=True
    )
    # 确定排名次序，处理平均分并列的情况（并列则共享同一排名）
    rank_dict = {}
    rank = 1
    prev_score = None
    for sid, avg in ranked_list:
        if prev_score is not None and abs(avg - prev_score) < 1e-6:
            # 平均分并列，赋予相同排名
            rank_dict[sid] = rank_dict.get(sid, rank)
        else:
            rank_dict[sid] = rank
        prev_score = avg
        rank += 1

    # 计算每个作品的逆序对数量
    inversion_counts = {sid: 0 for sid in score_data.keys()}
    # 将所有评分按评审者分组，方便比较同一评审者给出的相对顺序
    ratings_by_reviewer = {}
    all_ratings = Rating.query.all()
    for r in all_ratings:
        ratings_by_reviewer.setdefault(r.reviewer_id, []).append((r.target_id, r.innovation_score + r.professional_score))
    # 遍历每位评审者的评分列表，检查任意两作品在该评审者局部排序与全局排序的相对关系
    eps = 1e-6
    for rev, rated_list in ratings_by_reviewer.items():
        # 两两比较该评审者评分的作品对
        n = len(rated_list)
        for i in range(n):
            for j in range(i + 1, n):
                id_i, score_i = rated_list[i]
                id_j, score_j = rated_list[j]
                # 仅考虑都有提交且有平均分的数据
                if score_data[id_i]["avg"] is None or score_data[id_j]["avg"] is None:
                    continue
                avg_i = score_data[id_i]["avg"]
                avg_j = score_data[id_j]["avg"]
                if abs(avg_i - avg_j) < eps:
                    continue  # 全局平均分相等，不算作逆序
                # 全局排名比较结果
                global_comp = '>' if avg_i > avg_j else '<'
                # 该评审者本地评分比较结果
                if score_i == score_j:
                    local_comp = '='
                else:
                    local_comp = '>' if score_i > score_j else '<'
                if local_comp == '=':
                    continue  # 本地给两作品打分相同，跳过
                # 若全局和局部排序相反，则记录一次逆序现象
                if (global_comp == '>' and local_comp == '<') or (global_comp == '<' and local_comp == '>'):
                    inversion_counts[id_i] += 1
                    inversion_counts[id_j] += 1

    # 构建结果列表，仅包含有评分数据的作品
    for sid, data in score_data.items():
        if data["avg"] is None:
            # 跳过没有评分的作品（若有学生未收到任何评分）
            continue
        analysis_data.append({
            "student_id": sid,
            "name": data["name"],
            "average_score": round(data["avg"], 2),
            "variance": round(data["var"], 2) if data["var"] is not None else None,
            "rank": rank_dict.get(sid),
            "inversion_count": inversion_counts.get(sid, 0)
        })
    # 按排名顺序排序输出
    analysis_data.sort(key=lambda x: x["rank"])

    return jsonify(analysis_data), 200

# 教师分析接口 - 导出CSV文件
@app.route('/analysis/export', methods=['GET'])
def analysis_export():
    # 为简洁复用上面/analysis的大部分逻辑来计算统计数据
    projects = Project.query.filter_by(submitted=True).all()
    score_data = {}
    for proj in projects:
        sid = proj.student_id
        ratings = Rating.query.filter_by(target_id=sid).all()
        scores = [(r.innovation_score + r.professional_score) for r in ratings]
        if scores:
            avg_score = sum(scores) / len(scores)
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        else:
            avg_score = None
            variance = None
        score_data[sid] = {"name": proj.student.name, "avg": avg_score, "var": variance}
    ranked_list = sorted([(sid, data["avg"]) for sid, data in score_data.items() if data["avg"] is not None],
                         key=lambda x: x[1], reverse=True)
    rank_dict = {}
    rank = 1
    prev_score = None
    for sid, avg in ranked_list:
        if prev_score is not None and abs(avg - prev_score) < 1e-6:
            rank_dict[sid] = rank_dict.get(sid, rank)
        else:
            rank_dict[sid] = rank
        prev_score = avg
        rank += 1
    ratings_by_reviewer = {}
    all_ratings = Rating.query.all()
    for r in all_ratings:
        ratings_by_reviewer.setdefault(r.reviewer_id, []).append((r.target_id, r.innovation_score + r.professional_score))
    inversion_counts = {sid: 0 for sid in score_data.keys()}
    eps = 1e-6
    for rev, rated_list in ratings_by_reviewer.items():
        n = len(rated_list)
        for i in range(n):
            for j in range(i + 1, n):
                id_i, score_i = rated_list[i]
                id_j, score_j = rated_list[j]
                if score_data[id_i]["avg"] is None or score_data[id_j]["avg"] is None:
                    continue
                avg_i = score_data[id_i]["avg"]
                avg_j = score_data[id_j]["avg"]
                if abs(avg_i - avg_j) < eps:
                    continue
                global_comp = '>' if avg_i > avg_j else '<'
                if score_i == score_j:
                    local_comp = '='
                else:
                    local_comp = '>' if score_i > score_j else '<'
                if local_comp == '=':
                    continue
                if (global_comp == '>' and local_comp == '<') or (global_comp == '<' and local_comp == '>'):
                    inversion_counts[id_i] += 1
                    inversion_counts[id_j] += 1

    # 利用csv模块构造CSV输出
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Name", "Average Score", "Variance", "Rank", "Inversion Count"])
    for sid, data in score_data.items():
        if data["avg"] is None:
            continue
        writer.writerow([
            sid,
            data["name"],
            round(data["avg"], 2),
            round(data["var"], 2) if data["var"] is not None else None,
            rank_dict.get(sid),
            inversion_counts.get(sid, 0)
        ])
    csv_data = output.getvalue()
    # 通过Response返回CSV内容，设置内容类型和文件名
    return Response(csv_data, mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=analysis.csv"})

# 仅在直接运行app.py时启动Flask开发服务器
if __name__ == '__main__':
    app.run(debug=True)
