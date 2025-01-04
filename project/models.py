from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


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
    preferences = db.Column(db.String(500))
    pid = db.Column(db.Integer, db.ForeignKey("personnel.id"), unique=True)
    projects = db.relationship("Project", backref="user")
    comments = db.relationship("Comment", backref="user")

    def __repr__(self):
        return f"<User(id={self.id}, date_registered='{self.date_registered}')>"


class Project(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    school_year = db.Column(db.String(20), nullable=False)
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
    students = db.Column(db.Text)
    location = db.Column(db.String(50), nullable=False)
    # fieldtrip data
    fieldtrip_address = db.Column(db.Text)
    fieldtrip_ext_people = db.Column(db.String(200))
    fieldtrip_impact = db.Column(db.Text)
    #
    nb_students = db.Column(db.Integer, nullable=False)
    # links data
    link_t_1 = db.Column(db.String(100))
    link_1 = db.Column(db.String(200))
    link_t_2 = db.Column(db.String(100))
    link_2 = db.Column(db.String(200))
    link_t_3 = db.Column(db.String(100))
    link_3 = db.Column(db.String(200))
    link_t_4 = db.Column(db.String(100))
    link_4 = db.Column(db.String(200))
    # budget data for year 1
    budget_hse_1 = db.Column(db.Integer, default=0, nullable=False)
    budget_hse_c_1 = db.Column(db.Text)
    budget_exp_1 = db.Column(db.Integer, default=0, nullable=False)
    budget_exp_c_1 = db.Column(db.Text)
    budget_trip_1 = db.Column(db.Integer, default=0, nullable=False)
    budget_trip_c_1 = db.Column(db.Text)
    budget_int_1 = db.Column(db.Integer, default=0, nullable=False)
    budget_int_c_1 = db.Column(db.Text)
    # budget data for year 2
    budget_hse_2 = db.Column(db.Integer, default=0, nullable=False)
    budget_hse_c_2 = db.Column(db.Text)
    budget_exp_2 = db.Column(db.Integer, default=0, nullable=False)
    budget_exp_c_2 = db.Column(db.Text)
    budget_trip_2 = db.Column(db.Integer, default=0, nullable=False)
    budget_trip_c_2 = db.Column(db.Text)
    budget_int_2 = db.Column(db.Integer, default=0, nullable=False)
    budget_int_c_2 = db.Column(db.Text)
    #
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), nullable=False)
    validated_at = db.Column(db.DateTime)
    is_recurring = db.Column(db.String(10), default="Non", nullable=False)
    nb_comments = db.Column(db.Text, default="0", nullable=False)
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
    lock = db.Column(db.Boolean, default=False, nullable=False)
    sy_start = db.Column(db.DateTime, nullable=False)
    sy_end = db.Column(db.DateTime, nullable=False)
    sy_auto = db.Column(db.Boolean, default=True, nullable=False)
    lock_message = db.Column(db.Text)
    welcome_message = db.Column(db.Text)
