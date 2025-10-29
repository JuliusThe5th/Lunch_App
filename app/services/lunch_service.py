from app.extensions import db
from app.models import Student, TodayLunch, AvailableLunch, GivenLunch


def split_name(full_name):
    """Split full name into first name and surname, and return Student object"""
    name_parts = full_name.split(' ', 1)

    if len(name_parts) != 2:
        return None, {'error': 'Invalid name format'}, 400

    first_name, surname = name_parts

    student = Student.query.filter_by(name=first_name, surname=surname).first()

    if not student:
        return None, {'error': 'Student not found'}, 404

    return student, None, None


def give_lunch_to_pool(student_id):
    """Move lunch from TodayLunch to AvailableLunch pool"""
    daily_lunch = TodayLunch.query.filter_by(student_id=student_id).first()
    if not daily_lunch:
        return False, {'error': 'No lunch found for the user'}

    lunch_id = daily_lunch.lunch_id

    # Delete from TodayLunch
    db.session.delete(daily_lunch)

    # Add to AvailableLunch
    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).first()
    if available_lunch:
        available_lunch.quantity += 1
    else:
        available_lunch = AvailableLunch(lunch_id=lunch_id, quantity=1)
        db.session.add(available_lunch)

    db.session.commit()
    return True, {'lunch_id': lunch_id}


def transfer_lunch_directly(sender_id, recipient_id):
    """Transfer lunch directly from sender to recipient"""
    # Find sender's lunch
    sender_lunch = TodayLunch.query.filter_by(student_id=sender_id).first()
    if not sender_lunch:
        return False, {'error': 'Sender does not have a lunch to give'}

    # Check if recipient already has lunch
    existing_lunch = TodayLunch.query.filter_by(student_id=recipient_id).first()
    if existing_lunch:
        recipient = Student.query.get(recipient_id)
        return False, {'error': f'Student {recipient.name} {recipient.surname} already has a lunch assigned'}

    # Transfer lunch
    lunch_id = sender_lunch.lunch_id
    sender_lunch.student_id = recipient_id

    db.session.commit()
    return True, {'lunch_id': lunch_id}


def request_lunch_from_pool(student_id, lunch_id):
    """Request a lunch from the available pool"""
    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).with_for_update().first()

    if not available_lunch or available_lunch.quantity <= 0:
        return False, {'error': 'Requested lunch is not available'}

    # Check if student already has lunch
    daily_lunch = TodayLunch.query.filter_by(student_id=student_id).first()
    if daily_lunch:
        return False, {'error': 'Student already has a lunch assigned'}

    # Assign lunch to student
    available_lunch.quantity -= 1
    new_daily_lunch = TodayLunch(student_id=student_id, lunch_id=lunch_id)
    db.session.add(new_daily_lunch)

    db.session.commit()
    return True, {'lunch_id': lunch_id}


def mark_lunch_given(student_id):
    """Mark lunch as given (move from TodayLunch to GivenLunch)"""
    daily_lunch = TodayLunch.query.filter_by(student_id=student_id).first()
    if not daily_lunch:
        return False, {'error': 'Lunch data not found for the student'}

    lunch_id = daily_lunch.lunch_id

    # Remove from TodayLunch
    db.session.delete(daily_lunch)

    # Add to GivenLunch
    given_lunch = GivenLunch(student_id=student_id, lunch_id=lunch_id)
    db.session.add(given_lunch)

    db.session.commit()
    return True, {'lunch_id': lunch_id}

