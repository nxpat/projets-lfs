from datetime import date, datetime
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, String, Text, or_
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


class Personnel(db.Model, UserMixin):
    __tablename__ = "personnels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    firstname: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    user: Mapped["User | None"] = relationship("User", back_populates="p", uselist=False)
    projects: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="p", lazy=True
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "name" in kwargs:
            self.name = kwargs["name"].strip().title()
        if "firstname" in kwargs:
            self.firstname = kwargs["firstname"].strip().title()

    def __repr__(self):
        return f"<Personnel(id={self.id}, email='{self.email}', name='{self.name}', firstname='{self.firstname}', department='{self.department}', role='{self.role}')>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    date_registered: Mapped[datetime] = mapped_column(nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)
    new_messages: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)

    pid: Mapped[int | None] = mapped_column(ForeignKey("personnels.id"), unique=True)

    p: Mapped["Personnel | None"] = relationship("Personnel", back_populates="user")
    projects: Mapped[list["Project"]] = relationship(
        "Project", foreign_keys="Project.uid", back_populates="user"
    )
    comments: Mapped[list["ProjectComment"]] = relationship("ProjectComment", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, date_registered='{self.date_registered}')>"


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uid: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    school_year: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)

    start_date: Mapped[datetime] = mapped_column(nullable=False)
    end_date: Mapped[datetime | None] = mapped_column()

    axis: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[str] = mapped_column(String(200), nullable=False)

    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    indicators: Mapped[str | None] = mapped_column(Text)

    # Restored db.JSON explicitly:
    paths: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)
    skills: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)
    divisions: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)

    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    requirement: Mapped[str] = mapped_column(String(50), nullable=False)

    # Restored db.JSON explicitly:
    students: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)

    location: Mapped[str] = mapped_column(String(50), nullable=False)

    # fieldtrip data
    fieldtrip_address: Mapped[str | None] = mapped_column(Text)
    fieldtrip_ext_people: Mapped[str | None] = mapped_column(String(200))
    fieldtrip_impact: Mapped[str | None] = mapped_column(Text)
    nb_students: Mapped[int] = mapped_column(nullable=False)

    # links data
    link_t_1: Mapped[str | None] = mapped_column(String(100))
    link_1: Mapped[str | None] = mapped_column(String(200))
    link_t_2: Mapped[str | None] = mapped_column(String(100))
    link_2: Mapped[str | None] = mapped_column(String(200))
    link_t_3: Mapped[str | None] = mapped_column(String(100))
    link_3: Mapped[str | None] = mapped_column(String(200))
    link_t_4: Mapped[str | None] = mapped_column(String(100))
    link_4: Mapped[str | None] = mapped_column(String(200))

    # budget
    budget_id: Mapped[str | None] = mapped_column(String(50), index=True)

    # budget data for year 1
    budget_hse_1: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_hse_c_1: Mapped[str | None] = mapped_column(Text)
    budget_exp_1: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_exp_c_1: Mapped[str | None] = mapped_column(Text)
    budget_trip_1: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_trip_c_1: Mapped[str | None] = mapped_column(Text)
    budget_int_1: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_int_c_1: Mapped[str | None] = mapped_column(Text)

    # budget data for year 2
    budget_hse_2: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_hse_c_2: Mapped[str | None] = mapped_column(Text)
    budget_exp_2: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_exp_c_2: Mapped[str | None] = mapped_column(Text)
    budget_trip_2: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_trip_c_2: Mapped[str | None] = mapped_column(Text)
    budget_int_2: Mapped[int] = mapped_column(default=0, nullable=False)
    budget_int_c_2: Mapped[str | None] = mapped_column(Text)

    is_recurring: Mapped[bool] = mapped_column(default=False, nullable=False)

    modified_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column()
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Explicit relationships
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[uid], back_populates="projects"
    )
    modifier: Mapped["User"] = relationship("User", foreign_keys=[modified_by])
    validator: Mapped["User | None"] = relationship("User", foreign_keys=[validated_by])

    # Core relationships using back_populates
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )
    comments: Mapped[list["ProjectComment"]] = relationship(
        "ProjectComment", back_populates="project", cascade="all, delete-orphan"
    )
    history: Mapped[list["ProjectHistory"]] = relationship(
        "ProjectHistory",
        back_populates="project",
        order_by="ProjectHistory.updated_at.desc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Project(id={self.id}, title='{self.title}', user_id={self.uid})>"

    @property
    def members_departments(self):
        return list({member.department for member in self.members if member.department})

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
        return self.budget_exp + self.budget_trip + self.budget_int

    @property
    def budget_total_1(self) -> int:
        return self.budget_exp_1 + self.budget_trip_1 + self.budget_int_1

    @property
    def budget_total_2(self) -> int:
        return self.budget_exp_2 + self.budget_trip_2 + self.budget_int_2


class ProjectMember(db.Model):
    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    pid: Mapped[int] = mapped_column(ForeignKey("personnels.id"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Added explicit relationships to resolve both ends of back_populates
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    p: Mapped["Personnel"] = relationship("Personnel", back_populates="projects")


class ProjectHistory(db.Model):
    __tablename__ = "project_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    updater: Mapped["User"] = relationship("User", foreign_keys=[updated_by])
    project: Mapped["Project"] = relationship("Project", back_populates="history")

    start_date: Mapped[datetime | None] = mapped_column()
    end_date: Mapped[datetime | None] = mapped_column()
    nb_students: Mapped[int | None] = mapped_column()

    # budget
    budget_id: Mapped[str | None] = mapped_column(String(50))
    budget_hse_1: Mapped[int | None] = mapped_column()
    budget_hse_c_1: Mapped[str | None] = mapped_column(Text)
    budget_exp_1: Mapped[int | None] = mapped_column()
    budget_exp_c_1: Mapped[str | None] = mapped_column(Text)
    budget_trip_1: Mapped[int | None] = mapped_column()
    budget_trip_c_1: Mapped[str | None] = mapped_column(Text)
    budget_int_1: Mapped[int | None] = mapped_column()
    budget_int_c_1: Mapped[str | None] = mapped_column(Text)
    budget_hse_2: Mapped[int | None] = mapped_column()
    budget_hse_c_2: Mapped[str | None] = mapped_column(Text)
    budget_exp_2: Mapped[int | None] = mapped_column()
    budget_exp_c_2: Mapped[str | None] = mapped_column(Text)
    budget_trip_2: Mapped[int | None] = mapped_column()
    budget_trip_c_2: Mapped[str | None] = mapped_column(Text)
    budget_int_2: Mapped[int | None] = mapped_column()
    budget_int_c_2: Mapped[str | None] = mapped_column(Text)

    def __repr__(self):
        return f"<ProjectHistory {self.id} - Project ID: {self.project_id}, Updated By: {self.updated_by}, Status: {self.status}>"


class ProjectComment(db.Model):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    uid: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<ProjectComment(id={self.id}, message='{self.message}', user_id={self.uid}, project_id={self.project_id})>"


class Dashboard(db.Model):
    __tablename__ = "dashboard"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lock: Mapped[int] = mapped_column(default=0, nullable=False)
    lock_message: Mapped[str | None] = mapped_column(Text)
    welcome_message: Mapped[str | None] = mapped_column(Text)


class SchoolYear(db.Model):
    __tablename__ = "school_years"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sy: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    sy_start: Mapped[date] = mapped_column(nullable=False)
    sy_end: Mapped[date] = mapped_column(nullable=False)

    # Restored db.JSON explicitly:
    divisions: Mapped[list[Any]] = mapped_column(db.JSON, default=list, nullable=False)
    pe: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict, nullable=False)

    @property
    def nb_projects(self) -> int:
        """Dynamically count projects associated with this school year."""
        return Project.query.filter(Project.school_year == self.sy).count()


class QueuedAction(db.Model):
    __tablename__ = "queued_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uid: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Restored db.JSON explicitly:
    parameters: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, default=dict)
    options: Mapped[dict[str, Any] | None] = mapped_column(db.JSON, default=dict)
