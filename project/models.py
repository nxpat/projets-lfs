from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

from sqlalchemy import or_
from sqlalchemy.ext.hybrid import hybrid_property

db = SQLAlchemy()


class Personnel(db.Model, UserMixin):
    __tablename__ = "personnels"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    firstname = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, index=True)

    user = db.relationship("User", backref="p", uselist=False)
    projects = db.relationship("ProjectMember", backref="p", lazy=True)

    def __init__(self, **kwargs):
        super(Personnel, self).__init__(**kwargs)
        if "name" in kwargs:
            self.name = kwargs["name"].strip().title()
        if "firstname" in kwargs:
            self.firstname = kwargs["firstname"].strip().title()

    def __repr__(self):
        return f"<Personnel(id={self.id}, email='{self.email}', name='{self.name}', firstname='{self.firstname}', department='{self.department}', role='{self.role}')>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    password = db.Column(db.String(100), nullable=False)
    date_registered = db.Column(db.DateTime, nullable=False)
    preferences = db.Column(db.JSON, default=dict, nullable=False)
    new_messages = db.Column(db.JSON, default=list, nullable=False)

    pid = db.Column(db.Integer, db.ForeignKey("personnels.id"), unique=True)

    projects = db.relationship("Project", foreign_keys="Project.uid", backref="user")
    comments = db.relationship("ProjectComment", backref="user")

    def __repr__(self):
        return f"<User(id={self.id}, date_registered='{self.date_registered}')>"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, index=True)

    school_year = db.Column(db.String(20), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)

    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)

    axis = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(200), nullable=False)

    objectives = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    indicators = db.Column(db.Text)

    paths = db.Column(db.JSON, default=list, nullable=False)
    skills = db.Column(db.JSON, default=list, nullable=False)
    divisions = db.Column(db.JSON, default=list, nullable=False)

    mode = db.Column(db.String(50), nullable=False)
    requirement = db.Column(db.String(50), nullable=False)

    students = db.Column(db.JSON, default=list, nullable=False)

    location = db.Column(db.String(50), nullable=False)

    # fieldtrip data
    fieldtrip_address = db.Column(db.Text)
    fieldtrip_ext_people = db.Column(db.String(200))
    fieldtrip_impact = db.Column(db.Text)
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

    # budget
    budget_id = db.Column(db.String(50), index=True)

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

    is_recurring = db.Column(db.Boolean, default=False, nullable=False)

    modified_at = db.Column(db.DateTime, nullable=False, index=True)
    modified_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    validated_at = db.Column(db.DateTime)
    validated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    status = db.Column(db.String(50), nullable=False, index=True)

    # Explicit relationships
    modifier = db.relationship("User", foreign_keys=[modified_by])
    validator = db.relationship("User", foreign_keys=[validated_by])

    # Core relationships
    members = db.relationship("ProjectMember", backref="project", cascade="all, delete-orphan")
    comments = db.relationship("ProjectComment", backref="project", cascade="all, delete-orphan")
    history = db.relationship(
        "ProjectHistory",
        backref="project",
        order_by="ProjectHistory.updated_at.desc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project(id={self.id}, title='{self.title}', user_id={self.uid})>"

    @property
    def members_departments(self):
        return list(set([member.department for member in self.members if member.department]))

    @hybrid_property
    def has_budget(self) -> bool:
        """Python evaluation: Check if the project has any budget."""
        return any(
            v
            for v in (
                self.budget_hse_1,
                self.budget_exp_1,
                self.budget_trip_1,
                self.budget_int_1,
                self.budget_hse_2,
                self.budget_exp_2,
                self.budget_trip_2,
                self.budget_int_2,
            )
        )

    @has_budget.expression
    def has_budget(cls):
        """SQL evaluation."""
        return or_(
            cls.budget_hse_1 > 0,
            cls.budget_exp_1 > 0,
            cls.budget_trip_1 > 0,
            cls.budget_int_1 > 0,
            cls.budget_hse_2 > 0,
            cls.budget_exp_2 > 0,
            cls.budget_trip_2 > 0,
            cls.budget_int_2 > 0,
        )

    @property
    def budget_hse(self) -> int:
        return self.budget_hse_1 + self.budget_hse_2

    @property
    def budget_exp(self) -> int:
        return self.budget_exp_1 + self.budget_exp_2

    @property
    def budget_trip(self) -> int:
        return self.budget_trip_1 + self.budget_trip_2

    @property
    def budget_int(self) -> int:
        return self.budget_int_1 + self.budget_int_2

    @property
    def budget_total(self) -> int:
        # Notice we remove the parentheses here too!
        return self.budget_exp + self.budget_trip + self.budget_int

    @property
    def budget_total_1(self) -> int:
        return self.budget_exp_1 + self.budget_trip_1 + self.budget_int_1

    @property
    def budget_total_2(self) -> int:
        return self.budget_exp_2 + self.budget_trip_2 + self.budget_int_2


class ProjectMember(db.Model):
    __tablename__ = "project_members"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    pid = db.Column(db.Integer, db.ForeignKey("personnels.id"), primary_key=True)
    role = db.Column(db.String(50))
    department = db.Column(db.String(50), nullable=False, index=True)


class ProjectHistory(db.Model):
    __tablename__ = "project_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, index=True)

    updater = db.relationship("User", foreign_keys=[updated_by])

    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    nb_students = db.Column(db.Integer)

    # budget
    budget_id = db.Column(db.String(50))
    budget_hse_1 = db.Column(db.Integer)
    budget_hse_c_1 = db.Column(db.Text)
    budget_exp_1 = db.Column(db.Integer)
    budget_exp_c_1 = db.Column(db.Text)
    budget_trip_1 = db.Column(db.Integer)
    budget_trip_c_1 = db.Column(db.Text)
    budget_int_1 = db.Column(db.Integer)
    budget_int_c_1 = db.Column(db.Text)
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
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))
    posted_at = db.Column(db.DateTime, nullable=False)
    message = db.Column(db.Text, nullable=False)

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
    sy = db.Column(db.String(11), nullable=False, index=True)
    sy_start = db.Column(db.Date, nullable=False)
    sy_end = db.Column(db.Date, nullable=False)

    divisions = db.Column(db.JSON, default=list, nullable=False)
    pe = db.Column(db.JSON, default=dict, nullable=False)

    @property
    def nb_projects(self) -> int:
        """Dynamically count projects associated with this school year."""
        return Project.query.filter(Project.school_year == self.sy).count()


class QueuedAction(db.Model):
    __tablename__ = "queued_actions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey("users.id"))
    timestamp = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(30), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    parameters = db.Column(db.JSON, default=dict)
    options = db.Column(db.JSON, default=dict)
