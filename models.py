# models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

# 使用SQLAlchemy创建数据库实例
db = SQLAlchemy()

# 学生模型: 存储学生基本信息
# 为什么这么做: 每个学生有唯一ID和姓名。通过学生ID可以关联作品和评分记录。
# 如何测试: 初始化数据库后，可检查Student表是否正确插入20个学生记录。
class Student(db.Model):
    __tablename__ = 'student'
    id = Column(Integer, primary_key=True)         # 学生ID，主键
    name = Column(String(50), nullable=False)      # 学生姓名

    # 与Project(作品)表建立一对一关系
    project = relationship("Project", back_populates="student", uselist=False)
    # 建立与评分记录的关系，方便查询一个学生给出的评分和收到的评分
    reviews_given = relationship("Rating", foreign_keys="Rating.reviewer_id", back_populates="reviewer")
    reviews_received = relationship("Rating", foreign_keys="Rating.target_id", back_populates="target")

# 作品模型: 每个学生对应一个作品
# 为什么这么做: 独立的作品表用于标记作品提交状态和相关信息，与Student一对一关联。
# 如何测试: 提交作品接口调用后，检查Project表相应学生记录的submitted字段是否更新为True并记录时间。
class Project(db.Model):
    __tablename__ = 'project'
    # 以学生ID作为主键和外键，确保一对一关系（每个学生最多一个作品）
    student_id = Column(Integer, ForeignKey('student.id'), primary_key=True)
    submitted = Column(Boolean, default=False)     # 是否已提交作品
    submitted_at = Column(DateTime, nullable=True) # 最近提交时间戳

    student = relationship("Student", back_populates="project")  # 对应的学生对象

# 评分任务模型: 定义学生互评的任务分配
# 为什么这么做: 预先分配谁评谁，可确保每个学生评3个作品、每个作品被评3次，避免重复或遗漏。
# 如何测试: 初始化后，每个学生的 Assignment 应该有3条记录（作为评审者）且作为被评对象也有3条记录，可通过查询验证。
class Assignment(db.Model):
    __tablename__ = 'assignment'
    reviewer_id = Column(Integer, ForeignKey('student.id'), primary_key=True)  # 评审者(学生)ID
    target_id = Column(Integer, ForeignKey('student.id'), primary_key=True)    # 被评作品所属学生ID

    # 建立关系方便查询（一个学生的待评作品列表，及一个作品有哪些评审者）
    reviewer = relationship("Student", foreign_keys=[reviewer_id], backref="assignments_to_review")
    target = relationship("Student", foreign_keys=[target_id], backref="assignments_as_target")

# 评分记录模型: 存储学生对他人作品的评分
# 为什么这么做: 保存每次评分的详细信息，包括评审人、作品及两项评分（A-E已转为数值）。
# 如何测试: 学生调用评分接口后，对应的Rating记录应插入数据库，可查询验证总数是否正确(应有60条评分记录)。
class Rating(db.Model):
    __tablename__ = 'rating'
    id = Column(Integer, primary_key=True)               # 评分记录ID（自增主键）
    reviewer_id = Column(Integer, ForeignKey('student.id'))  # 评审者(学生)ID
    target_id = Column(Integer, ForeignKey('student.id'))    # 被评作品所属学生ID
    innovation_score = Column(Integer, nullable=False)       # 创新性评分(数值)
    professional_score = Column(Integer, nullable=False)     # 专业性评分(数值)

    # 与Student建立关系，方便通过对象属性访问
    reviewer = relationship("Student", foreign_keys=[reviewer_id], back_populates="reviews_given")
    target = relationship("Student", foreign_keys=[target_id], back_populates="reviews_received")
