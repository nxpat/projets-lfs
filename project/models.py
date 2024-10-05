from flask_login import UserMixin
from . import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    date_registered = db.Column(db.DateTime)
    firstname = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50))


class Project(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    objectives = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    date_1 = db.Column(db.DateTime, nullable=False)
    date_2 = db.Column(db.DateTime)
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
    students = db.Column(db.Integer, nullable=False)
    website = db.Column(db.String(500))
    fin_hse = db.Column(db.Integer, nullable=False)
    fin_hse_c = db.Column(db.Text)
    fin_exp = db.Column(db.Integer, nullable=False)
    fin_exp_c = db.Column(db.Text)
    fin_trip = db.Column(db.Integer, nullable=False)
    fin_trip_c = db.Column(db.Text)
    fin_int = db.Column(db.Integer, nullable=False)
    fin_int_c = db.Column(db.Text)
    created = db.Column(db.DateTime, nullable=False)
    modified = db.Column(db.DateTime, nullable=False)
    state = db.Column(db.String(50), nullable=False)
    validation = db.Column(db.DateTime)
    comments = db.Column(db.String(10), nullable=False)


class Comment(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    posted = db.Column(db.DateTime, nullable=False)


class Personnel(db.Model, UserMixin):
    email = db.Column(db.String(100), primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50))


class Dashboard(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    lock = db.Column(db.Boolean, nullable=False)
    sy_start = db.Column(db.DateTime, nullable=False)
    sy_end = db.Column(db.DateTime, nullable=False)
    sy_auto = db.Column(db.Boolean, nullable=False)
