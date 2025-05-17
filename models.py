# models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

# 使用SQLAlchemy创建数据库实例
db = SQLAlchemy()

# 学生模型: 存储学生基本信息
class Student(db.Model):
    __tablename__ = 'student'
    id = Column(String(20), primary_key=True)         # 学生ID，主键
    name = Column(String(50), nullable=False)      # 学生姓名
    group = Column(Integer, nullable=False)     # 学生组别
    class_id = Column(Integer, nullable=False)     # 学生班级
    project = relationship("Project", back_populates="student", uselist=False)
    ratings_given = relationship("Rating", back_populates="reviewer", foreign_keys="Rating.reviewer_id")
    def __repr__(self):
        return f"<Project student_id={self.student_id}, submitted={self.submitted}, submitted_at={self.submitted_at}>"

# 作品模型: 每个学生对应一个作品
class Project(db.Model):
    __tablename__ = 'project'
    # 以学生ID作为主键和外键，确保一对一关系（每个学生最多一个作品）
    student_id = Column(String(20), ForeignKey('student.id'), primary_key=True)
    submitted = Column(Boolean, default=False)     # 是否已提交作品
    submitted_at = Column(DateTime) # 最近提交时间戳
    student = relationship("Student", back_populates="project")  # 对应的学生对象

class GroupAssignment(db.Model):
    """互评任务分组模型，定义班级内评审小组与被评小组的对应关系"""
    __tablename__ = 'group_assignment'
    class_id = Column(Integer, primary_key=True)  # 班级ID（主键）
    reviewer_group = Column(Integer, primary_key=True)  # 评审组别（主键）
    target_group = Column(Integer, nullable=False)  

    def __repr__(self):
        return f"<GA {self.class_name} G{self.reviewer_group_id}→G{self.target_group_id}>"


class Rating(db.Model):
    '''
    单条评分记录：某学生reviewer_id对该班级的目标小组给出的分数
    '''
    __tablename__ = 'rating'
    id = Column(Integer, primary_key=True)
    reviewer_id = Column(String(20), ForeignKey('student.id'), nullable=False)  # 评审者ID
    reviewer_class = Column(Integer, nullable=False)  # 评审者班级
    reviewer_group = Column(Integer, nullable=False)  # 评审者组别
    target_group = Column(Integer, nullable=False)  # 被评审者组别
    innovation_score = db.Column(db.Integer, nullable=False)       # 创新得分
    professional_score = db.Column(db.Integer, nullable=False)     # 专业得分
    timestamp = db.Column(DateTime, default=datetime.now)  # 评分时间戳
    round = Column(Integer, nullable=False)  # 评分轮次
    reviewer = relationship("Student", back_populates="ratings_given", foreign_keys=[reviewer_id])  # 评审者对象
    def __repr__(self):
        return f"<Rating reviewer_id={self.reviewer_id}, target={self.target_class}-{self.target_group_id}, round={self.round}, scores=({self.innovation_score}, {self.professional_score})>"