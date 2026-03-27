from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Student, TodayLunch, AvailableLunch, GivenLunch
from app.services import (
    split_name,
    give_lunch_to_pool,
    transfer_lunch_directly,
    request_lunch_from_pool
)
from app.socketio_handlers import (
    broadcast_lunch_updates,
    broadcast_student_updates,
    broadcast_user_info_update
)

bp = Blueprint('lunch', __name__)


@bp.route('/give_lunch', methods=['POST'])
@jwt_required()
def give_lunch():
    """Give lunch to the available pool"""
    full_name = get_jwt_identity()

    try:
        student, error, status = split_name(full_name)
        if error:
            return jsonify(error), status

        success, result = give_lunch_to_pool(student.id)
        if not success:
            return jsonify(result), 404

        # Broadcast real-time updates
        broadcast_lunch_updates()
        broadcast_student_updates()
        broadcast_user_info_update(full_name)

        return jsonify({
            'message': f'Lunch {result["lunch_id"]} given successfully',
            'student': f"{student.name} {student.surname}"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to give lunch: {str(e)}'}), 500


@bp.route('/give_lunch_direct', methods=['POST'])
@jwt_required()
def give_lunch_direct():
    """Direct lunch gifting - authenticated user gives their lunch to another student"""
    authenticated_user = get_jwt_identity()
    print(f"Authenticated user: {authenticated_user} is giving their lunch to another student")

    try:
        sender_student, error, status = split_name(authenticated_user)
        if error:
            return jsonify(error), status

        data = request.get_json()
        recipient_student_id = data.get('student_id')

        if not recipient_student_id:
            return jsonify({'error': 'student_id is required'}), 400

        try:
            recipient_student_id = int(recipient_student_id)
        except ValueError:
            return jsonify({'error': 'student_id must be a number'}), 400

        recipient_student = Student.query.get(recipient_student_id)
        if not recipient_student:
            return jsonify({'error': 'Recipient student not found'}), 404

        success, result = transfer_lunch_directly(sender_student.id, recipient_student_id)
        if not success:
            return jsonify(result), 400

        print(f"User {authenticated_user} successfully transferred lunch {result['lunch_id']} to student {recipient_student.name} {recipient_student.surname}")

        return jsonify({
            'message': f'Lunch {result["lunch_id"]} successfully transferred',
            'sender': {
                'name': sender_student.name,
                'surname': sender_student.surname,
                'full_name': f"{sender_student.name} {sender_student.surname}"
            },
            'recipient': {
                'id': recipient_student.id,
                'name': recipient_student.name,
                'surname': recipient_student.surname,
                'full_name': f"{recipient_student.name} {recipient_student.surname}"
            },
            'lunch_id': result['lunch_id']
        }), 200

    except Exception as e:
        print(f"Error in direct lunch transfer by {authenticated_user}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Failed to transfer lunch: {str(e)}'}), 500


@bp.route('/request_lunch', methods=['POST'])
@jwt_required()
def request_lunch():
    """Request a lunch from the available pool"""
    full_name = get_jwt_identity()

    student, error, status = split_name(full_name)
    if error:
        return jsonify(error), status

    data = request.get_json()
    lunch_id = data.get('lunch_id')

    if not lunch_id:
        return jsonify({'error': 'lunch_id is required'}), 400

    try:
        lunch_id = int(lunch_id)
    except ValueError:
        return jsonify({'error': 'lunch_id must be a number'}), 400

    try:
        success, result = request_lunch_from_pool(student.id, lunch_id)
        if not success:
            return jsonify(result), 404 if 'not available' in result['error'] else 400

        # Broadcast real-time updates
        broadcast_lunch_updates()
        broadcast_student_updates()
        broadcast_user_info_update(full_name)

        return jsonify({'message': f'Lunch {lunch_id} assigned to {student.name} successfully'}), 200

    except Exception as e:
        print(f"Database commit failed: {e}")
        db.session.rollback()
        return jsonify({'error': 'Database error occurred'}), 500


# DEPRECATED GET ROUTES (Use Socket.IO instead)
@bp.route('/user-info', methods=['GET'])
@jwt_required()
def get_user_info():
    """DEPRECATED: Use Socket.IO 'get_user_info' event instead"""
    full_name = get_jwt_identity()
    print(f"DEPRECATED GET /api/user-info called for {full_name}")

    try:
        student, error, status = split_name(full_name)
        if error:
            return jsonify(error), status

        today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

        return jsonify({
            'name': f"{student.name} {student.surname}",
            'lunch': {
                'hasLunch': today_lunch is not None,
                'number': today_lunch.lunch_id if today_lunch else None
            },
            'deprecated': True,
            'message': 'Please use Socket.IO get_user_info event instead'
        }), 200

    except Exception as e:
        print(f"Error getting student info: {e}")
        return jsonify({'error': 'Failed to retrieve student information'}), 500


@bp.route('/lunches', methods=['GET'])
def get_lunches():
    """DEPRECATED: Use Socket.IO 'get_lunches' event instead"""
    print("DEPRECATED GET /api/lunches called")
    lunches = AvailableLunch.query.all()
    lunch_data = {f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}
    return jsonify({
        **lunch_data,
        'deprecated': True,
        'message': 'Please use Socket.IO get_lunches event instead'
    }), 200


@bp.route('/recentLunches', methods=['GET'])
@jwt_required()
def get_recent_lunches():
    """DEPRECATED: Use Socket.IO 'get_recent_lunches' event instead"""
    print("DEPRECATED GET /api/recentLunches called")
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

        return jsonify({
            'recent_lunches': lunch_list,
            'deprecated': True,
            'message': 'Please use Socket.IO get_recent_lunches event instead'
        }), 200

    except Exception as e:
        print(f"Error getting recent lunches: {e}")
        return jsonify({'error': 'Failed to retrieve recent lunches'}), 500

