from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.models import Student, TodayLunch

bp = Blueprint('students', __name__)


@bp.route('/students', methods=['GET'])
@jwt_required()
def get_students():
    """DEPRECATED: Use Socket.IO 'get_students' event instead"""
    print("DEPRECATED GET /api/students called")
    try:
        students = Student.query.all()
        student_list = []

        for student in students:
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

            if today_lunch is None:
                student_data = {
                    'id': student.id,
                    'full_name': f"{student.name} {student.surname}",
                    'picture': student.pictureURL,
                }
                student_list.append(student_data)

        return jsonify({
            'students': student_list,
            'count': len(student_list),
            'deprecated': True,
            'message': 'Please use Socket.IO get_students event instead'
        }), 200

    except Exception as e:
        print(f"Error getting students: {e}")
        return jsonify({'error': 'Failed to retrieve students'}), 500


@bp.route('/getAll', methods=['GET'])
@jwt_required()
def get_all_students():
    """DEPRECATED: Use Socket.IO 'get_all_students' event instead"""
    print("DEPRECATED GET /api/getAll called")
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

        return jsonify({
            'users': student_list,
            'deprecated': True,
            'message': 'Please use Socket.IO get_all_students event instead'
        }), 200

    except Exception as e:
        print(f"Error getting all students: {e}")
        return jsonify({'error': 'Failed to retrieve students'}), 500

