from flask_login import UserMixin
from datetime import datetime
from . import db


class Personnel(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    firstname = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50))
    user = db.relationship("User", backref="p", uselist=False)

    def __repr__(self):
        return f"<Personnel(id={self.id}, email='{self.email}', name='{self.name}', firstname='{self.firstname}', department='{self.department}', role='{self.role}')>"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    password = db.Column(db.String(100), nullable=False)
    date_registered = db.Column(db.DateTime)
    pid = db.Column(db.Integer, db.ForeignKey("personnel.id"), unique=True)
    projects = db.relationship("Project", backref="user")
    comments = db.relationship("Comment", backref="user")

    def __repr__(self):
        return f"<User(id={self.id}, date_registered='{self.date_registered}')>"


class Project(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    objectives = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    departments = db.Column(db.String(200), nullable=False)
    teachers = db.Column(db.Text, nullable=False)
    axis = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(200), nullable=False)
    paths = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.String(100), nullable=False)
    divisions = db.Column(db.String(200), nullable=False)
    indicators = db.Column(db.Text)
    mode = db.Column(db.String(50), nullable=False)
    requirement = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    nb_students = db.Column(db.Integer, nullable=False)
    website = db.Column(db.String(500))
    budget_hse = db.Column(db.Integer, default=0, nullable=False)
    budget_hse_c = db.Column(db.Text)
    budget_exp = db.Column(db.Integer, default=0, nullable=False)
    budget_exp_c = db.Column(db.Text)
    budget_trip = db.Column(db.Integer, default=0, nullable=False)
    budget_trip_c = db.Column(db.Text)
    budget_int = db.Column(db.Integer, default=0, nullable=False)
    budget_int_c = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), nullable=False)
    validation = db.Column(db.DateTime)
    nb_comments = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    comments = db.relationship("Comment", backref="project")

    def __repr__(self):
        return f"<Project(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class Comment(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message = db.Column(db.Text, nullable=False)
    posted_at = db.Column(db.DateTime, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    def __repr__(self):
        return f"<Comment(id={self.id}, message='{self.message}', user_id={self.user_id}, project_id={self.project_id})>"


class Dashboard(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    lock = db.Column(db.Boolean, nullable=False)
    sy_start = db.Column(db.DateTime, nullable=False)
    sy_end = db.Column(db.DateTime, nullable=False)
    sy_auto = db.Column(db.Boolean, default=True, nullable=False)
