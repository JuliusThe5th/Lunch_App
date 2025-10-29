from app.extensions import db


class AvailableLunch(db.Model):
    __tablename__ = 'available_lunches'
    lunch_id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer)

