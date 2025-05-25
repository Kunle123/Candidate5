from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, TIMESTAMP
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class CVProfile(Base):
    __tablename__ = 'cv_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    email = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    work_experiences = relationship('WorkExperience', back_populates='profile', cascade='all, delete-orphan')
    education = relationship('Education', back_populates='profile', cascade='all, delete-orphan')
    skills = relationship('Skill', back_populates='profile', cascade='all, delete-orphan')
    projects = relationship('Project', back_populates='profile', cascade='all, delete-orphan')
    certifications = relationship('Certification', back_populates='profile', cascade='all, delete-orphan')

class WorkExperience(Base):
    __tablename__ = 'work_experiences'
    id = Column(Integer, primary_key=True)
    cv_profile_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'))
    company = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    start_date = Column(Text, nullable=False)
    end_date = Column(Text, nullable=False)
    description = Column(Text)
    order_index = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('cv_profile_id', 'order_index'),)
    profile = relationship('CVProfile', back_populates='work_experiences')

class Education(Base):
    __tablename__ = 'education'
    id = Column(Integer, primary_key=True)
    cv_profile_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'))
    institution = Column(Text, nullable=False)
    degree = Column(Text, nullable=False)
    field = Column(Text)
    start_date = Column(Text)
    end_date = Column(Text)
    description = Column(Text)
    order_index = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('cv_profile_id', 'order_index'),)
    profile = relationship('CVProfile', back_populates='education')

class Skill(Base):
    __tablename__ = 'skills'
    id = Column(Integer, primary_key=True)
    cv_profile_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'))
    skill = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint('cv_profile_id', 'skill'),)
    profile = relationship('CVProfile', back_populates='skills')

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    cv_profile_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'))
    name = Column(Text, nullable=False)
    description = Column(Text)
    order_index = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('cv_profile_id', 'order_index'),)
    profile = relationship('CVProfile', back_populates='projects')

class Certification(Base):
    __tablename__ = 'certifications'
    id = Column(Integer, primary_key=True)
    cv_profile_id = Column(Integer, ForeignKey('cv_profiles.id', ondelete='CASCADE'))
    name = Column(Text, nullable=False)
    issuer = Column(Text)
    year = Column(Text)
    order_index = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('cv_profile_id', 'order_index'),)
    profile = relationship('CVProfile', back_populates='certifications') 