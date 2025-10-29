from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app.extensions import socketio, db
from app.models import Student, TodayLunch, AvailableLunch, GivenLunch
from app.services import split_name


def validate_jwt_token(token):
    """Validate JWT token and return the user identity"""
    try:
        decoded_token = decode_token(token)
        return decoded_token['sub']
    except Exception as e:
        print(f"JWT validation error: {e}")
        return None


# Socket.IO Event Handlers
@socketio.on('connect')
def handle_connect(auth):
    """Handle client connection with JWT authentication"""
    if auth and 'token' in auth:
        user_identity = validate_jwt_token(auth['token'])
        if user_identity:
            join_room('lunch_updates')
            join_room(f'user_{user_identity}')
            emit('connected', {'message': 'Connected to lunch updates', 'user': user_identity})
            print(f"User {user_identity} connected to Socket.IO")
        else:
            emit('error', {'message': 'Invalid authentication token'})
            return False
    else:
        join_room('lunch_updates')
        emit('connected', {'message': 'Connected to lunch updates'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    leave_room('lunch_updates')
    print("Client disconnected from Socket.IO")


@socketio.on('get_user_info')
def handle_get_user_info(data):
    """Socket.IO handler for user info"""
    token = data.get('token') if data else None
    if not token:
        emit('user_info_error', {'error': 'Authentication token required'})
        return

    user_identity = validate_jwt_token(token)
    if not user_identity:
        emit('user_info_error', {'error': 'Invalid authentication token'})
        return

    try:
        student, error, status = split_name(user_identity)
        if error:
            emit('user_info_error', {'error': 'Student not found'})
            return

        today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

        user_info = {
            'name': f"{student.name} {student.surname}",
            'lunch': {
                'hasLunch': today_lunch is not None,
                'number': today_lunch.lunch_id if today_lunch else None
            }
        }

        emit('user_info_response', user_info)

    except Exception as e:
        print(f"Error getting student info: {e}")
        emit('user_info_error', {'error': 'Failed to retrieve student information'})


@socketio.on('get_lunches')
def handle_get_lunches(data=None):
    """Socket.IO handler for available lunches"""
    try:
        lunches = AvailableLunch.query.all()
        lunch_data = {f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}
        emit('lunches_response', lunch_data)

    except Exception as e:
        print(f"Error getting lunches: {e}")
        emit('lunches_error', {'error': 'Failed to retrieve lunch data'})


@socketio.on('get_students')
def handle_get_students(data):
    """Socket.IO handler for students without lunch"""
    token = data.get('token') if data else None
    if not token:
        emit('students_error', {'error': 'Authentication token required'})
        return

    user_identity = validate_jwt_token(token)
    if not user_identity:
        emit('students_error', {'error': 'Invalid authentication token'})
        return

    try:
        students = Student.query.all()
        student_list = []

        for student in students:
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

            student_data = {
                'id': student.id,
                'full_name': f"{student.name} {student.surname}",
                'picture': student.pictureURL,
                'has_lunch': today_lunch is not None,
                'has_card': student.card_id is not None,
            }
            student_list.append(student_data)

        response_data = {
            'students': student_list,
            'count': len(student_list)
        }

        emit('students_response', response_data)

    except Exception as e:
        print(f"Error getting students: {e}")
        emit('students_error', {'error': 'Failed to retrieve students'})


@socketio.on('get_all_students')
def handle_get_all_students(data):
    """Socket.IO handler for all students"""
    token = data.get('token') if data else None
    if not token:
        emit('all_students_error', {'error': 'Authentication token required'})
        return

    user_identity = validate_jwt_token(token)
    if not user_identity:
        emit('all_students_error', {'error': 'Invalid authentication token'})
        return

    try:
        students = Student.query.all()
        student_list = []

        for student in students:
            student_data = {
                'full_name': f"{student.name} {student.surname}",
                'picture': student.pictureURL,
                'has_lunch': TodayLunch.query.filter_by(student_id=student.id).first() is not None
            }
            student_list.append(student_data)

        response_data = {
            'users': student_list,
        }

        emit('all_students_response', response_data)

    except Exception as e:
        print(f"Error getting all students: {e}")
        emit('all_students_error', {'error': 'Failed to retrieve students'})


@socketio.on('get_recent_lunches')
def handle_get_recent_lunches(data):
    """Socket.IO handler for recent lunches"""
    token = data.get('token') if data else None
    if not token:
        emit('recent_lunches_error', {'error': 'Authentication token required'})
        return

    user_identity = validate_jwt_token(token)
    if not user_identity:
        emit('recent_lunches_error', {'error': 'Invalid authentication token'})
        return

    try:
        recent_lunches = db.session.query(
            GivenLunch, Student
        ).join(Student, GivenLunch.student_id == Student.id) \
            .order_by(GivenLunch.timestamp.desc()) \
            .limit(10).all()

        lunch_list = []
        for given_lunch, student in recent_lunches:
            lunch_data = {
                'student_name': f"{student.name} {student.surname}",
                'lunch_id': given_lunch.lunch_id,
                'timestamp': given_lunch.timestamp.strftime('%H:%M:%S')
            }
            lunch_list.append(lunch_data)

        response_data = {
            'recent_lunches': lunch_list
        }

        emit('recent_lunches_response', response_data)

    except Exception as e:
        print(f"Error getting recent lunches: {e}")
        emit('recent_lunches_error', {'error': 'Failed to retrieve recent lunches'})


# Broadcast functions
def broadcast_lunch_updates():
    """Broadcast updated lunch data to all connected clients"""
    try:
        lunches = AvailableLunch.query.all()
        lunch_data = {f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}
        socketio.emit('lunches_response', lunch_data, room='lunch_updates')
        print("Broadcasted lunch updates to all clients")
    except Exception as e:
        print(f"Error broadcasting lunch updates: {e}")


def broadcast_student_updates():
    """Broadcast updated student data to all connected clients"""
    try:
        students = Student.query.all()
        student_list = []
        all_students_list = []

        for student in students:
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
            has_lunch = today_lunch is not None

            if not has_lunch:
                student_data = {
                    'id': student.id,
                    'full_name': f"{student.name} {student.surname}",
                    'picture': student.pictureURL,
                }
                student_list.append(student_data)

            all_student_data = {
                'full_name': f"{student.name} {student.surname}",
                'picture': student.pictureURL,
                'has_lunch': has_lunch
            }
            all_students_list.append(all_student_data)

        socketio.emit('students_response', {
            'students': student_list,
            'count': len(student_list)
        }, room='lunch_updates')

        socketio.emit('all_students_response', {
            'users': all_students_list,
        }, room='lunch_updates')

        print("Broadcasted student updates to all clients")
    except Exception as e:
        print(f"Error broadcasting student updates: {e}")


def broadcast_recent_lunches():
    """Broadcast updated recent lunches to all connected clients"""
    try:
        recent_lunches = db.session.query(
            GivenLunch, Student
        ).join(Student, GivenLunch.student_id == Student.id) \
            .order_by(GivenLunch.timestamp.desc()) \
            .limit(10).all()

        lunch_list = []
        for given_lunch, student in recent_lunches:
            lunch_data = {
                'student_name': f"{student.name} {student.surname}",
                'lunch_id': given_lunch.lunch_id,
                'timestamp': given_lunch.timestamp.strftime('%H:%M:%S')
            }
            lunch_list.append(lunch_data)

        socketio.emit('recent_lunches_response', {
            'recent_lunches': lunch_list
        }, room='lunch_updates')

        print("Broadcasted recent lunches updates to all clients")
    except Exception as e:
        print(f"Error broadcasting recent lunches: {e}")


def broadcast_user_info_update(user_identity):
    """Broadcast user info update to a specific user"""
    try:
        student, error, status = split_name(user_identity)
        if error:
            return

        today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

        user_info = {
            'name': f"{student.name} {student.surname}",
            'lunch': {
                'hasLunch': today_lunch is not None,
                'number': today_lunch.lunch_id if today_lunch else None
            }
        }

        socketio.emit('user_info_response', user_info, room=f'user_{user_identity}')
        print(f"Broadcasted user info update to {user_identity}")
    except Exception as e:
        print(f"Error broadcasting user info update: {e}")

