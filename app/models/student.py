from app.extensions import db


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    pictureURL = db.Column(db.String(200))
    card_id = db.Column(db.String(100), unique=True)

