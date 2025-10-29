from app.extensions import db


class GivenLunch(db.Model):
    __tablename__ = 'given_lunches'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', name='fk_given_lunch_student_id'),
        nullable=False
    )
    lunch_id = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    student = db.relationship('Student', backref='given_lunches')

