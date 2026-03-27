from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Student, TodayLunch
from app.services import (
    mark_lunch_given,
    get_current_date_str,
    should_clear_database,
    export_lunch_history,
    clear_existing_data,
    process_pdf
)
import os
import datetime
from functools import wraps

bp = Blueprint('admin', __name__)


def admin_required(fn):
    """Decorator to check if user is admin"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        # JWT extension skips token processing for OPTIONS preflight by default.
        # Bypass admin identity checks here and let the route return preflight response.
        if request.method == 'OPTIONS':
            return fn(*args, **kwargs)

        identity = get_jwt_identity()
        # Find student by name to check if they're admin
        name_parts = identity.split(' ', 1)
        if len(name_parts) < 2:
            return jsonify({'error': 'Invalid user identity'}), 401
        
        first_name, surname = name_parts
        student = Student.query.filter_by(name=first_name, surname=surname).first()
        
        if not student or not student.isAdmin:
            return jsonify({'error': 'Admin access required'}), 403
        
        return fn(*args, **kwargs)
    return wrapper


@bp.route('/upload', methods=['POST', 'OPTIONS'])
def upload_pdf():
    """Upload and process PDF file with lunch data"""
    # Handle OPTIONS preflight request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and file.filename.endswith('.pdf'):
        try:
            # Create today's date folder
            current_date = get_current_date_str()
            today_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], current_date)
            os.makedirs(today_folder, exist_ok=True)

            # Save file with timestamp
            timestamp = datetime.datetime.now().strftime('%H-%M-%S')
            filename = f"{timestamp}_{file.filename}"
            filepath = os.path.join(today_folder, filename)
            file.save(filepath)
            print(f"Uploaded PDF saved to: {filepath}")

            # Check if we need to clear the database (new day)
            if should_clear_database():
                print("New day detected - clearing database")
                history_folder = os.path.join('LunchHistory', current_date)
                os.makedirs(history_folder, exist_ok=True)

                export_lunch_history(history_folder)
                clear_existing_data()
                print("Database cleared for new day")
            else:
                print("Same day - keeping existing data")

            # Process the PDF
            student_count, page_data_counts = process_pdf(filepath, current_app.config['UPLOAD_FOLDER'])

            if student_count is None:
                return jsonify({'error': 'Could not extract any valid data from the PDF'}), 400

            return jsonify({
                'message': 'PDF processed and database updated successfully',
                'new_entries_added': student_count,
                'total_entries_processed': sum(page_data_counts),
                'pages_processed': len(page_data_counts),
                'entries_per_page': page_data_counts,
                'file_saved_as': filename
            }), 200

        except Exception as e:
            print(f"Error during PDF processing: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .pdf files are allowed'}), 400


@bp.route('/lunch', methods=['POST', 'OPTIONS'])
@admin_required
def get_lunch_by_card():
    """Mark lunch as given using card UID (for card reader integration)"""
    # Handle OPTIONS preflight request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({'error': 'Invalid JSON data or no data provided'}), 400

    hashed_card_uid = data.get('card_uid')

    if not hashed_card_uid:
        return jsonify({'error': 'card_uid is required'}), 400

    # Find student by hashed card_id
    student = Student.query.filter_by(card_id=hashed_card_uid).first()
    if not student:
        return jsonify({'error': 'Student not found for the provided card UID'}), 404

    # Mark lunch as given
    success, result = mark_lunch_given(student.id)
    if not success:
        return jsonify({
            'name': student.name,
            'surname': student.surname,
            'error': result['error']
        }), 404

    return jsonify({
        'name': student.name,
        'surname': student.surname,
        'Lunch': result['lunch_id'],
    }), 200


@bp.route('/assign_card', methods=['POST', 'OPTIONS'])
@admin_required
def assign_card():
    """Assign card UID to a student"""
    # Handle OPTIONS preflight request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # Try to get JSON data, force=True allows parsing even without Content-Type header
    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({'error': 'Invalid JSON data or no data provided'}), 400

    name = data.get('name')
    surname = data.get('surname')
    card_uid = data.get('card_uid')

    if not name or not surname or not card_uid:
        return jsonify({'error': 'Name, surname and card_uid are required'}), 400

    # Find student by name and surname
    student = Student.query.filter_by(name=name, surname=surname).first()
    if not student:
        return jsonify({'error': f'Student {name} {surname} not found'}), 404

    # Check if card_uid is already assigned
    existing_card = Student.query.filter_by(card_id=card_uid).first()
    if existing_card:
        return jsonify({'error': 'This card is already assigned to another student'}), 400

    # Assign card_uid to student
    try:
        student.card_id = card_uid
        db.session.commit()
        return jsonify({
            'message': 'Card assigned successfully',
            'name': student.name,
            'surname': student.surname,
            'card_uid': card_uid
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to assign card: {str(e)}'}), 500

