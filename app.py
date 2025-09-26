from flask import Flask, request, jsonify, redirect, url_for, session
from models import db, Student, TodayLunch, AvailableLunch, GivenLunch
from flask_migrate import Migrate
from pyngrok import ngrok, conf
import pandas as pd
import hashlib
import os
import datetime
import pytz
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required, decode_token
from datetime import timedelta
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure the app
app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']  # Accept tokens from both headers and cookies
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_COOKIE_SECURE'] = False  # Set to False for development (localhost)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Disable CSRF protection for development
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'  # Change from 'None' to 'Lax' for localhost
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

jwt = JWTManager(app)

# JWT Error handlers for better debugging
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    print("JWT ERROR: Token expired")
    return jsonify({"error": "Token has expired"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    print(f"JWT ERROR: Invalid JWT token: {error}")
    return jsonify({"error": "Invalid token"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    print(f"JWT ERROR: Missing JWT token: {error}")
    return jsonify({"error": "Authorization token required"}), 401

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return False

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

CORS(app, resources={r"/*": {
    "origins": [FRONTEND_URL],  # Be explicit with protocol
    "supports_credentials": True,
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "expose_headers": ["Authorization"],
}})

# Initialize the database
db.init_app(app)
migrate = Migrate(app, db)

# Set ngrok authtoken
conf.get_default().auth_token = os.getenv('NGROK_AUTH_TOKEN')

socketio = SocketIO(app, cors_allowed_origins=[FRONTEND_URL],
                   async_mode='threading',
                   logger=False,
                   engineio_logger=False)

# Helper function to validate JWT token from Socket.IO
def validate_jwt_token(token):
    """Validate JWT token and return the user identity"""
    try:
        from flask_jwt_extended import decode_token
        decoded_token = decode_token(token)
        return decoded_token['sub']  # 'sub' contains the identity
    except Exception as e:
        print(f"JWT validation error: {e}")
        return None

@socketio.on('connect')
def handle_connect(auth):
    """Handle client connection with JWT authentication"""
    if auth and 'token' in auth:
        user_identity = validate_jwt_token(auth['token'])
        if user_identity:
            join_room('lunch_updates')
            join_room(f'user_{user_identity}')  # User-specific room
            emit('connected', {'message': 'Connected to lunch updates', 'user': user_identity})
            print(f"User {user_identity} connected to Socket.IO")
        else:
            emit('error', {'message': 'Invalid authentication token'})
            return False
    else:
        # For backwards compatibility, allow connection without auth for now
        join_room('lunch_updates')
        emit('connected', {'message': 'Connected to lunch updates'})

@socketio.on('disconnect')
def handle_disconnect():
    leave_room('lunch_updates')
    print("Client disconnected from Socket.IO")

# =========================
# POST ROUTES
# =========================

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    user_data = request.json
    try:
        # Extract full name from Google response
        # Make sure we get the complete name
        full_name = user_data.get('fullName')
        picture = user_data.get('picture')

        if not full_name:
            return jsonify({'error': 'Invalid user data - missing name components'}), 400

        # Get result from split_name
        result = split_name(full_name)

        # Check if result is a tuple (error response)
        if isinstance(result, tuple):
            response_json, status_code = result

            # If it's a 404 (student not found), create new student
            if status_code == 404:
                # Split name into components
                name_parts = full_name.split(' ', 1)
                if len(name_parts) != 2:
                    return jsonify({'error': 'Invalid name format - need both first name and surname'}), 400

                first_name, surname = name_parts

                # Create new student
                try:
                    student = Student(
                        name=first_name,
                        surname=surname,
                        pictureURL=picture
                    )
                    db.session.add(student)
                    db.session.commit()
                    print(f"Created new student: {first_name} {surname}")
                except Exception as e:
                    db.session.rollback()
                    print(f"Failed to create student: {e}")
                    return jsonify({'error': 'Failed to create new student'}), 500
            else:
                # For other errors, return the error response
                return result
        else:
            # If not a tuple, it's a valid Student object
            student = result
        # Create JWT token with full name
        access_token = create_access_token(identity=full_name)

        response = jsonify({
            'message': 'Authentication successful',
            'name': full_name,  # Send back constructed full name
            'picture': picture,
        })

        response.set_cookie(
            'access_token_cookie',
            access_token,
            secure=False,  # Set to False for development (localhost)
            httponly=False,
            samesite='Lax',  # Changed from 'None' to 'Lax' for localhost
            domain=None,
            max_age=30 * 24 * 60 * 60
        )

        return response

    except Exception as e:
        print(f"Authentication error: {e}")
        return jsonify({'error': 'Authentication failed'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """
    Clear the JWT token cookie to log out the user
    """
    response = jsonify({'message': 'Successfully logged out'})

    # Unset the JWT cookie
    response.delete_cookie(
        'access_token_cookie',
        secure=False,  # Set to False for development (localhost)
        httponly=True,
        samesite='Lax'  # Changed from 'None' to 'Lax' for localhost
    )

    return response, 200

# Route to upload PDF file
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and file.filename.endswith('.pdf'):
        try:
            # Create today's date folder
            current_date = get_current_date_str()
            today_folder = os.path.join(app.config['UPLOAD_FOLDER'], current_date)
            os.makedirs(today_folder, exist_ok=True)

            # Save file with timestamp to prevent overwriting
            timestamp = datetime.datetime.now().strftime('%H-%M-%S')
            filename = f"{timestamp}_{file.filename}"
            filepath = os.path.join(today_folder, filename)
            file.save(filepath)
            print(f"Uploaded PDF saved to: {filepath}")

            # Check if we need to clear the database (new day)
            should_clear = should_clear_database()
            if should_clear:
                print("New day detected - clearing database")
                # Create LunchHistory folder if it doesn't exist
                history_folder = os.path.join('LunchHistory', current_date)
                os.makedirs(history_folder, exist_ok=True)

                # Export lunch history before clearing data
                export_lunch_history(history_folder)

                # Clear existing data
                clear_existing_data()
                print("Database cleared for new day")
            else:
                print("Same day - keeping existing data")

            # Process the uploaded PDF file
            import pdfplumber
            import re

            all_data = []
            page_data_counts = []
            header_found = False

            with pdfplumber.open(filepath) as pdf:
                print(f"PDF has {len(pdf.pages)} pages")

                for page_num, page in enumerate(pdf.pages):
                    print(f"Processing page {page_num + 1}")
                    page_entry_count = 0
                    text = page.extract_text()

                    if text:
                        lines = text.split('\n')

                        if not header_found:
                            # Find the header line containing O1, O2, O3 on first occurrence
                            for i, line in enumerate(lines):
                                if 'O1' in line and 'O2' in line and 'O3' in line:
                                    header_found = True
                                    header_line_idx = i
                                    print(f"Found header line: {line}")
                                    # Process lines after header on first page
                                    lines = lines[header_line_idx + 1:]
                                    break

                        # Process all lines if header was found (on this or previous page)
                        if header_found:
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue

                                # Match pattern: Surname FirstName 1 0 0 (or similar)
                                match = re.match(r'([^\d]+)\s+([^\d]+)\s+([01])\s+([01])\s+([01])', line)
                                if match:
                                    surname = match.group(1).strip()  # First part is surname
                                    first_name = match.group(2).strip()  # Second part is first name
                                    lunch1, lunch2, lunch3 = match.group(3), match.group(4), match.group(5)

                                    # Look up student by both name and surname
                                    student = Student.query.filter_by(name=first_name, surname=surname).first()
                                    if not student:
                                        # Create new student with separated name and surname
                                        student = Student(name=first_name, surname=surname)
                                        db.session.add(student)
                                        db.session.commit()

                                    # Add entries for each lunch that has a '1'
                                    if lunch1 == '1':
                                        all_data.append({"student_id": student.id, "LunchNumber": 1})
                                        page_entry_count += 1
                                    if lunch2 == '1':
                                        all_data.append({"student_id": student.id, "LunchNumber": 2})
                                        page_entry_count += 1
                                    if lunch3 == '1':
                                        all_data.append({"student_id": student.id, "LunchNumber": 3})
                                        page_entry_count += 1

                    page_data_counts.append(page_entry_count)
                    print(f"Found {page_entry_count} entries on page {page_num + 1}")

            # Check if we extracted any data
            if not all_data:
                return jsonify({'error': 'Could not extract any valid data from the PDF'}), 400

            # Process the extracted data
            student_count = 0
            for item in all_data:
                # Get the student using the stored student_id from all_data
                student = Student.query.get(item["student_id"])
                if not student:
                    continue  # Skip if student not found

                # Delete any existing lunch entry for this student
                existing_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
                if existing_lunch:
                    db.session.delete(existing_lunch)

                # Create new lunch entry
                daily_lunch = TodayLunch(student_id=student.id, lunch_id=item["LunchNumber"])
                db.session.add(daily_lunch)
                student_count += 1

            db.session.commit()
            return jsonify({
                'message': 'PDF processed and database updated successfully',
                'new_entries_added': student_count,
                'total_entries_processed': len(all_data),
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

@app.route('/lunch', methods=['POST'])
def get_lunch_by_card():
    data = request.get_json()
    hashed_card_uid = data.get('card_uid')

    if not hashed_card_uid:
        return jsonify({'error': 'card_uid is required'}), 400

    # Find student by the hashed card_id
    student = Student.query.filter_by(card_id=hashed_card_uid).first()
    if not student:
        return jsonify({'error': 'Student not found for the provided card UID'}), 404

    # Find the lunch assigned to the student
    daily_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
    if not daily_lunch:
        return jsonify({'error': 'Lunch data not found for the student'}), 404

    lunch_id = daily_lunch.lunch_id

    # Remove the lunch from TodayLunch
    db.session.delete(daily_lunch)

    # Add the lunch to GivenLunch
    given_lunch = GivenLunch(student_id=student.id, lunch_id=lunch_id)
    db.session.add(given_lunch)

    # Commit the changes
    db.session.commit()

    return jsonify({'message': f'Lunch {lunch_id} given to student {student.name} successfully'}), 200

@app.route('/api/give_lunch', methods=['POST'])
@jwt_required()
def give_lunch():
    # Get full name from JWT
    full_name = get_jwt_identity()

    try:
        student = split_name(full_name)

        # Find their lunch for today
        daily_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
        if not daily_lunch:
            return jsonify({'error': 'No lunch found for the user'}), 404

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

        # Broadcast real-time updates to all connected clients
        broadcast_lunch_updates()
        broadcast_student_updates()
        broadcast_user_info_update(full_name)

        return jsonify({
            'message': f'Lunch {lunch_id} given successfully',
            'student': f"{student.name} {student.surname}"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to give lunch: {str(e)}'}), 500

@app.route('/api/give_lunch_direct', methods=['POST'])
@jwt_required()
def give_lunch_direct():
    """
    Direct lunch gifting - authenticated user gives their lunch to another student
    Requires student_id in request body (the recipient student)
    JWT protected route - authenticated user is the sender
    """
    # Get authenticated user's name from JWT token
    authenticated_user = get_jwt_identity()
    print(f"Authenticated user: {authenticated_user} is giving their lunch to another student")

    try:
        # Get the authenticated user's student record
        sender_student = split_name(authenticated_user)
        if not isinstance(sender_student, Student):
            return sender_student  # Return error response from split_name

        # Find the sender's lunch for today
        sender_lunch = TodayLunch.query.filter_by(student_id=sender_student.id).first()
        if not sender_lunch:
            return jsonify({'error': 'You do not have a lunch to give'}), 404

        data = request.get_json()
        recipient_student_id = data.get('student_id')

        if not recipient_student_id:
            return jsonify({'error': 'student_id is required'}), 400

        try:
            recipient_student_id = int(recipient_student_id)
        except ValueError:
            return jsonify({'error': 'student_id must be a number'}), 400

        # Find the recipient student by ID
        recipient_student = Student.query.get(recipient_student_id)
        if not recipient_student:
            return jsonify({'error': 'Recipient student not found'}), 404

        # Check if recipient already has a lunch
        existing_lunch = TodayLunch.query.filter_by(student_id=recipient_student_id).first()
        if existing_lunch:
            return jsonify({'error': f'Student {recipient_student.name} {recipient_student.surname} already has a lunch assigned'}), 400

        lunch_id = sender_lunch.lunch_id

        # Transfer the lunch from sender to recipient
        sender_lunch.student_id = recipient_student_id  # Change ownership

        db.session.commit()

        print(f"User {authenticated_user} successfully transferred lunch {lunch_id} to student {recipient_student.name} {recipient_student.surname}")

        return jsonify({
            'message': f'Lunch {lunch_id} successfully transferred',
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
            'lunch_id': lunch_id
        }), 200

    except Exception as e:
        print(f"Error in direct lunch transfer by {authenticated_user}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Failed to transfer lunch: {str(e)}'}), 500

@app.route('/api/request_lunch', methods=['POST'])
@jwt_required()
def request_lunch():
    full_name = get_jwt_identity()

    # Get the student object
    student = split_name(full_name)
    if not isinstance(student, Student):
        return student

    data = request.get_json()
    lunch_id = data.get('lunch_id')

    if not lunch_id:
        return jsonify({'error': 'lunch_id is required'}), 400

    try:
        lunch_id = int(lunch_id)
    except ValueError:
        return jsonify({'error': 'lunch_id must be a number'}), 400

    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).with_for_update().first()

    if not available_lunch or available_lunch.quantity <= 0:
        return jsonify({'error': 'Requested lunch is not available'}), 404

    daily_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
    if daily_lunch:
        return jsonify({'error': 'Student already has a lunch assigned'}), 400

    available_lunch.quantity -= 1
    new_daily_lunch = TodayLunch(student_id=student.id, lunch_id=lunch_id)
    db.session.add(new_daily_lunch)

    try:
        db.session.commit()

        # Broadcast real-time updates to all connected clients
        broadcast_lunch_updates()
        broadcast_student_updates()
        broadcast_user_info_update(full_name)

        return jsonify({'message': f'Lunch {lunch_id} assigned to {student.name} successfully'}), 200
    except Exception as e:
        print(f"Database commit failed: {e}")
        db.session.rollback()
        return jsonify({'error': 'Database error occurred'}), 500

@app.route('/assign_card', methods=['POST'])
def assign_card():
    data = request.get_json()
    student_name = data.get('student_name')
    card_uid = data.get('card_uid')

    if not student_name or not card_uid:
        return jsonify({'error': 'Both student_name and card_uid are required'}), 400

    # Find student by name
    student = Student.query.filter_by(name=student_name).first()
    if not student:
        return jsonify({'error': f'Student {student_name} not found'}), 404

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
            'student': student.name,
            'card_uid': card_uid
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to assign card: {str(e)}'}), 500

# =========================
# REAL-TIME UPDATE FUNCTIONS
# =========================

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
        # Broadcast students without lunch
        students = Student.query.all()
        student_list = []
        all_students_list = []

        for student in students:
            # Check if student has a lunch assigned today
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
            has_lunch = today_lunch is not None

            # For students without lunch list
            if not has_lunch:
                student_data = {
                    'id': student.id,
                    'full_name': f"{student.name} {student.surname}",
                    'picture': student.pictureURL,
                }
                student_list.append(student_data)

            # For all students list
            all_student_data = {
                'full_name': f"{student.name} {student.surname}",
                'picture': student.pictureURL,
                'has_lunch': has_lunch
            }
            all_students_list.append(all_student_data)

        # Broadcast both lists
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
        student = split_name(user_identity)
        if not isinstance(student, Student):
            return

        # Get today's lunch information
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

# =========================
# SOCKET.IO EVENT HANDLERS (replacing GET routes)
# =========================

@socketio.on('get_user_info')
def handle_get_user_info(data):
    """Socket.IO handler for user info (replaces /api/user-info GET)"""
    token = data.get('token') if data else None
    if not token:
        emit('user_info_error', {'error': 'Authentication token required'})
        return

    user_identity = validate_jwt_token(token)
    if not user_identity:
        emit('user_info_error', {'error': 'Invalid authentication token'})
        return

    try:
        student = split_name(user_identity)
        if not isinstance(student, Student):
            emit('user_info_error', {'error': 'Student not found'})
            return

        # Get today's lunch information
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
    """Socket.IO handler for available lunches (replaces /api/lunches GET)"""
    try:
        lunches = AvailableLunch.query.all()
        lunch_data = {f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}

        # Emit to the requesting client
        emit('lunches_response', lunch_data)

    except Exception as e:
        print(f"Error getting lunches: {e}")
        emit('lunches_error', {'error': 'Failed to retrieve lunch data'})

@socketio.on('get_students')
def handle_get_students(data):
    """Socket.IO handler for students without lunch (replaces /api/students GET)"""
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
            # Check if student has a lunch assigned today
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

            # Only include students who DON'T have a lunch
            if today_lunch is None:
                student_data = {
                    'id': student.id,
                    'full_name': f"{student.name} {student.surname}",
                    'picture': student.pictureURL,
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
    """Socket.IO handler for all students (replaces /api/getAll GET)"""
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
    """Socket.IO handler for recent lunches (replaces /api/recentLunches GET)"""
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

# =========================
# GET ROUTES (DEPRECATED - Use Socket.IO events instead)
# =========================

@app.route('/api/user-info', methods=['GET'])
@jwt_required()
def get_user_info():
    """
    DEPRECATED: Use Socket.IO 'get_user_info' event instead
    Endpoint to get current user information and lunch status
    """
    # Get the full name from JWT token
    full_name = get_jwt_identity()
    print(f"DEPRECATED GET /api/user-info called for {full_name}")
    try:
        student = split_name(full_name)

        # Get today's lunch information
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
        return jsonify({
            'error': 'Failed to retrieve student information'
        }), 500

@app.route('/api/lunches', methods=['GET'])
def get_lunches():
    """
    DEPRECATED: Use Socket.IO 'get_lunches' event instead
    """
    print("DEPRECATED GET /api/lunches called")
    lunches = AvailableLunch.query.all()
    lunch_data = {f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}
    return jsonify({
        **lunch_data,
        'deprecated': True,
        'message': 'Please use Socket.IO get_lunches event instead'
    }), 200

@app.route('/api/students', methods=['GET'])
@jwt_required()
def get_students():
    """
    DEPRECATED: Use Socket.IO 'get_students' event instead
    """
    print("DEPRECATED GET /api/students called")
    try:
        students = Student.query.all()
        student_list = []

        for student in students:
            # Check if student has a lunch assigned today
            today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

            # Only include students who DON'T have a lunch
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

@app.route('/api/getAll', methods=['GET'])
@jwt_required()
def get_all_students():
    """
    DEPRECATED: Use Socket.IO 'get_all_students' event instead
    """
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

@app.route('/api/recentLunches', methods=['GET'])
@jwt_required()
def get_recent_lunches():
    """
    DEPRECATED: Use Socket.IO 'get_recent_lunches' event instead
    """
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

# =========================
# HELPER FUNCTIONS
# =========================

def get_current_date_str():
    # Get current date in EU format (DD-MM-YYYY)
    prague_tz = pytz.timezone('Europe/Prague')
    current_date = datetime.datetime.now(prague_tz)
    return current_date.strftime('%d-%m-%Y')

def should_clear_database():
    """Check if we should clear the database (new day started)"""
    try:
        prague_tz = pytz.timezone('Europe/Prague')
        current_date = datetime.datetime.now(prague_tz).date()

        # Get the date of the last lunch entry from GivenLunch
        last_given_lunch = GivenLunch.query.order_by(GivenLunch.timestamp.desc()).first()

        # If there are no given lunches, check TodayLunch
        if not last_given_lunch:
            today_lunch = TodayLunch.query.first()
            if not today_lunch:
                # If both tables are empty, only clear if there's no data at all
                student_count = Student.query.count()
                return student_count == 0
            return False

        last_lunch_date = last_given_lunch.timestamp.date()
        return current_date > last_lunch_date

    except Exception as e:
        print(f"Error checking database date: {e}")
        return False  # Default to not clearing on error

def export_lunch_history(history_folder):
    """Export lunch history to an Excel file."""
    # Query the given lunches and join with student data
    given_lunches = db.session.query(
        Student.name, GivenLunch.lunch_id, GivenLunch.timestamp
    ).join(Student, Student.id == GivenLunch.student_id) \
        .order_by(Student.name).all()

    print(f"Given lunches data: {given_lunches}")  # Debugging

    if given_lunches:
        # Convert the data to a DataFrame with time in 24-hour format
        data = [
            {
                'name': name,
                'lunch': lunch_id,
                'timestamp': timestamp.strftime('%H:%M:%S')  # Time in 24-hour format
            }
            for name, lunch_id, timestamp in given_lunches
        ]
        df = pd.DataFrame(data)

        # Get the date of the first given lunch
        first_given_lunch = db.session.query(GivenLunch.timestamp).order_by(GivenLunch.timestamp).first()
        print(f"First given lunch timestamp: {first_given_lunch}")  # Debugging

        if first_given_lunch:
            date_str = first_given_lunch.timestamp.strftime('%d-%m-%Y')  # EU format for the file name
            file_name = f"lunches {date_str}.xlsx"
            file_path = os.path.join(history_folder, file_name)

            # Save the DataFrame to an Excel file
            print(f"Saving file to: {file_path}")  # Debugging
            df.to_excel(file_path, index=False)
        else:
            print("No given lunches found to export.")
    else:
        print("No given lunches data available.")

def clear_existing_data():
    """Clear existing lunch data from the database."""
    db.session.query(TodayLunch).delete()
    db.session.commit()

    db.session.query(AvailableLunch).delete()
    db.session.commit()

    db.session.query(GivenLunch).delete()
    db.session.commit()

    db.session.query(AvailableLunch).update({AvailableLunch.quantity: 0})
    db.session.commit()
    print("Existing data cleared from database")

def split_name(full_name):
    # Split into first name and surname
    name_parts = full_name.split(' ', 1)

    if len(name_parts) != 2:
        return jsonify({'error': 'Invalid name format'}), 400

    first_name, surname = name_parts

    # Find student by name and surname
    student = Student.query.filter_by(name=first_name, surname=surname).first()

    if not student:
        return jsonify({'error': 'Student not found'}), 404
    else:
        return student

if __name__ == '__main__':
    # Ensure DB tables exist for dev (prevents "no such table" errors)
    with app.app_context():
        try:
            db.create_all()
            print("Database tables ensured.")
        except Exception as e:
            print(f"db.create_all failed: {e}")

    # Start ngrok only when explicitly enabled (prevents Flask CLI import crashes)
    if os.getenv('ENABLE_NGROK') == '1':
        try:
            public_url = ngrok.connect(
                addr="http://127.0.0.1:5000",
                domain="lamb-kind-preferably.ngrok-free.app"
            )
            print(f' * ngrok tunnel "{public_url}" -> "http://127.0.0.1:5000"')
        except Exception as e:
            print(f"Ngrok start skipped/failed: {e}")

    # Use only socketio.run() for Flask-SocketIO apps
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
