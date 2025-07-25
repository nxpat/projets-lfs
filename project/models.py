from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Personnel(db.Model, UserMixin):
    __tablename__ = "personnels"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    firstname = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50), nullable=False)

    user = db.relationship("User", backref="p", uselist=False)
    projects = db.relationship("ProjectMember", backref="p", lazy=True)

    def __repr__(self):
        return f"<Personnel(id={self.id}, email='{self.email}', name='{self.name}', firstname='{self.firstname}', department='{self.department}', role='{self.role}')>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    password = db.Column(db.String(100), nullable=False)
    date_registered = db.Column(db.DateTime, nullable=False)
    preferences = db.Column(db.String(500))
    new_messages = db.Column(db.String(100))
    pid = db.Column(db.Integer, db.ForeignKey("personnels.id"), unique=True)

    projects = db.relationship("Project", backref="user")
    comments = db.relationship("ProjectComment", backref="user")

    def __repr__(self):
        return f"<User(id={self.id}, date_registered='{self.date_registered}')>"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    school_year = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    objectives = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    departments = db.Column(db.String(200), nullable=False)
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
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))
    #
    modified_at = db.Column(db.DateTime, nullable=False)
    modified_by = db.Column(db.Integer, nullable=False)
    validated_at = db.Column(db.DateTime)
    validated_by = db.Column(db.Integer)
    status = db.Column(db.String, nullable=False)

    # relationships
    members = db.relationship(
        "ProjectMember", backref="project", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "ProjectComment", backref="project", cascade="all, delete-orphan"
    )
    # relationship to ProjectHistory, ordered by updated_at
    history = db.relationship(
        "ProjectHistory",
        backref="project",
        order_by="ProjectHistory.updated_at.desc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project(id={self.id}, title='{self.title}', user_id={self.uid})>"

    def has_budget(self) -> bool:
        """Check if the budget attributes are greater than zero."""
        return (
            self.budget_hse_1 > 0
            or self.budget_exp_1 > 0
            or self.budget_trip_1 > 0
            or self.budget_int_1 > 0
            or self.budget_hse_2 > 0
            or self.budget_exp_2 > 0
            or self.budget_trip_2 > 0
            or self.budget_int_2 > 0
        )

    def budget_hse(self) -> int:
        """Calculate school year budget for HSE budget."""
        return self.budget_hse_1 + self.budget_hse_2

    def budget_exp(self) -> int:
        """Calculate school year budget for expenditure budget."""
        return self.budget_exp_1 + self.budget_exp_2

    def budget_trip(self) -> int:
        """Calculate school year budget for trip budget."""
        return self.budget_trip_1 + self.budget_trip_2

    def budget_int(self) -> int:
        """Calculate school year budget for intervention budget."""
        return self.budget_int_1 + self.budget_int_2


# Project - Personnel junction table
class ProjectMember(db.Model):
    __tablename__ = "project_members"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    pid = db.Column(db.Integer, db.ForeignKey("personnels.id"), primary_key=True)
    role = db.Column(db.String)


class ProjectHistory(db.Model):
    """Snapshots of the project data whenever a change occurs"""

    __tablename__ = "project_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String, nullable=False)
    #
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    nb_students = db.Column(db.Integer)
    # budget data for year 1
    budget_hse_1 = db.Column(db.Integer)
    budget_hse_c_1 = db.Column(db.Text)
    budget_exp_1 = db.Column(db.Integer)
    budget_exp_c_1 = db.Column(db.Text)
    budget_trip_1 = db.Column(db.Integer)
    budget_trip_c_1 = db.Column(db.Text)
    budget_int_1 = db.Column(db.Integer)
    budget_int_c_1 = db.Column(db.Text)
    # budget data for year 2
    budget_hse_2 = db.Column(db.Integer)
    budget_hse_c_2 = db.Column(db.Text)
    budget_exp_2 = db.Column(db.Integer)
    budget_exp_c_2 = db.Column(db.Text)
    budget_trip_2 = db.Column(db.Integer)
    budget_trip_c_2 = db.Column(db.Text)
    budget_int_2 = db.Column(db.Integer)
    budget_int_c_2 = db.Column(db.Text)

    def __repr__(self):
        return f"<ProjectHistory {self.id} - Project ID: {self.project_id}, Updated By: {self.updated_by}, Status: {self.status}>"


class ProjectComment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    posted_at = db.Column(db.DateTime, nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))

    def __repr__(self):
        return f"<ProjectComment(id={self.id}, message='{self.message}', user_id={self.uid}, project_id={self.project_id})>"


class Dashboard(db.Model):
    __tablename__ = "dashboard"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lock = db.Column(db.Integer, default=0, nullable=False)
    lock_message = db.Column(db.Text)
    welcome_message = db.Column(db.Text)


class SchoolYear(db.Model):
    __tablename__ = "school_years"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sy_start = db.Column(db.Date, nullable=False)
    sy_end = db.Column(db.Date, nullable=False)
    sy = db.Column(db.String(11), nullable=False)
    nb_projects = db.Column(db.Integer, default=0, nullable=False)
    divisions = db.Column(db.String, nullable=False)


class QueuedAction(db.Model):
    __tablename__ = "queued_actions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(20), unique=True)
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))
    timestamp = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String, nullable=False)
    action_type = db.Column(db.String, nullable=False)
    parameters = db.Column(db.String)
    options = db.Column(db.String)
