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
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from datetime import timedelta
from flask_cors import CORS

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
    print(f"JWT HEADER: {jwt_header}")
    print(f"JWT PAYLOAD: {jwt_payload}")
    return jsonify({"error": "Token has expired"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    print(f"JWT ERROR: Invalid JWT token: {error}")
    print(f"JWT ERROR TYPE: {type(error)}")
    return jsonify({"error": "Invalid token"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    print(f"JWT ERROR: Missing JWT token: {error}")
    print(f"JWT ERROR TYPE: {type(error)}")
    return jsonify({"error": "Authorization token required"}), 401

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    print(f"JWT CHECK: Token blocklist check - Header: {jwt_header}, Payload: {jwt_payload}")
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


@app.before_request
def log_request_info():
    print('\n=== Request Info ===')
    print(f'Headers: {dict(request.headers)}')
    print(f'Cookies: {request.cookies}')
    print(f'Data: {request.get_json(silent=True)}')
    print('===================\n')

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
            httponly=True,
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
        samesite='Lax',  # Changed from 'None' to 'Lax' for localhost
        domain=None
    )

    return response, 200

@app.route('/api/user-info', methods=['GET'])
@jwt_required()
def get_user_info():
    """
    Endpoint to get current user information and lunch status
    Uses Student model and TodayLunch relationship
    """
    # Get the full name from JWT token
    full_name = get_jwt_identity()
    print(full_name)
    try:
        student = split_name(full_name)

        # Get today's lunch information
        today_lunch = TodayLunch.query.filter_by(student_id=student.id).first()

        return jsonify({
            'name': f"{student.name} {student.surname}",
            'lunch': {
                'hasLunch': today_lunch is not None,
                'number': today_lunch.lunch_id if today_lunch else None
            }
        }), 200

    except Exception as e:
        print(f"Error getting student info: {e}")
        return jsonify({
            'error': 'Failed to retrieve student information'
        }), 500

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

@app.route('/api/lunches', methods=['GET'])
def get_lunches():
    lunches = AvailableLunch.query.all()
    print({f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches})
    return jsonify({f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}), 200


@app.route('/api/students', methods=['GET'])
@jwt_required()
def get_students():
    """
    Get list of students who don't have lunch assigned
    JWT protected route
    """
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
            'count': len(student_list)
        }), 200

    except Exception as e:
        print(f"Error getting students: {e}")
        return jsonify({'error': 'Failed to retrieve students'}), 500

@app.route('/api/getAll', methods=['GET'])
@jwt_required()
def get_all_students():
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

            print(student_list)

        return jsonify({
            'users': student_list,
        }), 200

    except Exception as e:
        print(f"Error getting all students: {e}")
        return jsonify({'error': 'Failed to retrieve students'}), 500

@app.route('/api/recentLunches', methods=['GET'])
@jwt_required()
def get_recent_lunches():
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
            'recent_lunches': lunch_list
        }), 200

    except Exception as e:
        print(f"Error getting recent lunches: {e}")
        return jsonify({'error': 'Failed to retrieve recent lunches'}), 500

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
        return jsonify({
            'message': f'Lunch {lunch_id} given successfully',
            'student': f"{student.name} {student.surname}"  # Fixed: use student.name instead of student.first_name
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

def split_name(full_name):
    # Debug logging
    print(f"DEBUG: Full name received: '{full_name}'")
    print(f"DEBUG: Full name type: {type(full_name)}")
    print(f"DEBUG: Full name repr: {repr(full_name)}")

    # Split into first name and surname
    name_parts = full_name.split(' ', 1)
    print(f"DEBUG: Name parts: {name_parts}")

    if len(name_parts) != 2:
        print(f"DEBUG: Invalid name format - expected 2 parts, got {len(name_parts)}")
        return jsonify({'error': 'Invalid name format'}), 400

    first_name, surname = name_parts
    print(f"DEBUG: First name: '{first_name}', Surname: '{surname}'")

    # Find student by name and surname
    student = Student.query.filter_by(name=first_name, surname=surname).first()
    print(f"DEBUG: Student found: {student}")

    if not student:
        print(f"DEBUG: No student found with name='{first_name}' and surname='{surname}'")
        # Let's also check what students exist
        all_students = Student.query.all()
        print(f"DEBUG: All students in database:")
        for s in all_students:
            print(f"  - ID: {s.id}, Name: '{s.name}', Surname: '{s.surname}'")
        return jsonify({'error': 'Student not found'}), 404
    else:
        print(f"DEBUG: Found student: {student.name} {student.surname}")
        return student


@app.route('/api/request_lunch', methods=['POST'])
@jwt_required()
def request_lunch():
    full_name = get_jwt_identity()
    print(f"JWT SUCCESS: Full name: {full_name}")

    # Get the student object
    student = split_name(full_name)
    if not isinstance(student, Student):  # Handle error responses from split_name
        print(f"ERROR: split_name returned non-Student object: {student}")
        return student

    print(f"SUCCESS: Found student: {student.name} {student.surname} (ID: {student.id})")

    data = request.get_json()
    print(f"Request data: {data}")

    lunch_id = data.get('lunch_id')  # Match the frontend key name
    print(f"Extracted lunch_id: {lunch_id}")

    if not lunch_id:
        print("ERROR: lunch_id is missing from request")
        return jsonify({'error': 'lunch_id is required'}), 400

    try:
        lunch_id = int(lunch_id)  # Convert string to integer
        print(f"Converted lunch_id to int: {lunch_id}")
    except ValueError:
        print(f"ERROR: lunch_id conversion failed for value: {lunch_id}")
        return jsonify({'error': 'lunch_id must be a number'}), 400

    print(f"Looking for available lunch with ID: {lunch_id}")
    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).with_for_update().first()
    print(f"Available lunch found: {available_lunch}")

    if not available_lunch:
        print("ERROR: No available lunch found")
        # Let's see what lunches are available
        all_lunches = AvailableLunch.query.all()
        print(f"All available lunches: {[(l.lunch_id, l.quantity) for l in all_lunches]}")
        return jsonify({'error': 'Requested lunch is not available'}), 404

    if available_lunch.quantity <= 0:
        print(f"ERROR: Available lunch quantity is {available_lunch.quantity}")
        return jsonify({'error': 'Requested lunch is not available'}), 404

    print(f"Checking if student {student.id} already has a lunch...")
    daily_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
    print(f"Existing daily lunch: {daily_lunch}")

    if daily_lunch:
        print(f"ERROR: Student already has lunch {daily_lunch.lunch_id}")
        return jsonify({'error': 'Student already has a lunch assigned'}), 400

    print(f"Processing lunch assignment: reducing quantity from {available_lunch.quantity} to {available_lunch.quantity - 1}")
    available_lunch.quantity -= 1

    new_daily_lunch = TodayLunch(student_id=student.id, lunch_id=lunch_id)
    db.session.add(new_daily_lunch)
    print(f"Added new daily lunch: {new_daily_lunch}")

    try:
        db.session.commit()
        print("Database commit successful")
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

    app.run(debug=True, use_reloader=False)