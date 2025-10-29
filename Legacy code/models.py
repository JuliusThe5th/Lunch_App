from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    pictureURL = db.Column(db.String(200))
    card_id = db.Column(db.String(100), unique=True)

class AvailableLunch(db.Model):
    __tablename__ = 'available_lunches'
    lunch_id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer )  # Ensure quantity is not nullable

class TodayLunch(db.Model):
    __tablename__ = 'today_lunch'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', name='fk_today_lunch_student_id'),
        nullable=False
    )
    lunch_id = db.Column(db.Integer, nullable=False)  # Remove foreign key constraint

    student = db.relationship('Student', backref='today_lunch')
    # Remove the lunch relationship since there's no FK constraint


class GivenLunch(db.Model):
    __tablename__ = 'given_lunches'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', name='fk_given_lunch_student_id'),
        nullable=False
    )
    lunch_id = db.Column( db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    student = db.relationship('Student', backref='given_lunches')
