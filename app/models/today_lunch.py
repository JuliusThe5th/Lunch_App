from app.extensions import db


class TodayLunch(db.Model):
    __tablename__ = 'today_lunch'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id', name='fk_today_lunch_student_id'),
        nullable=False
    )
    lunch_id = db.Column(db.Integer, nullable=False)

    student = db.relationship('Student', backref='today_lunch')

