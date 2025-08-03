from flask import Flask, request, jsonify, redirect, url_for, session
from google.oauth2 import id_token
from google.auth.transport import requests  # Add this import
from models import db, Student, TodayLunch, AvailableLunch, GivenLunch
from flask_migrate import Migrate
from pyngrok import ngrok, conf
from authlib.integrations.flask_client import OAuth
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
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = True
app.config['JWT_COOKIE_CSRF_PROTECT'] = True
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

jwt = JWTManager(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')


CORS(app, resources={r"/*": {"origins": [FRONTEND_URL], "supports_credentials": True}})

# Initialize the database
db.init_app(app)
migrate = Migrate(app, db)

# Set ngrok authtoken
conf.get_default().auth_token = os.getenv('NGROK_AUTH_TOKEN')


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
            secure=True,
            httponly=True,
            samesite='None',
            domain=None,
            max_age=30 * 24 * 60 * 60
        )

        return response

    except Exception as e:
        print(f"Authentication error: {e}")
        return jsonify({'error': 'Authentication failed'}), 401


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
        # Split the full name into first name and surname
        # Assuming the format is "name surname"
        name_parts = full_name.split(' ', 1)
        if len(name_parts) != 2:
            return jsonify({
                'error': 'Invalid name format'
            }), 400

        first_name, surname = name_parts

        # Find student by both name and surname
        student = Student.query.filter_by(name=first_name, surname=surname).first()

        if not student:
            return jsonify({
                'error': 'Student not found'
            }), 404

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

@app.route('/lunches', methods=['GET'])
def get_lunches():
    lunches = AvailableLunch.query.all()
    return jsonify({f"lunch {lunch.lunch_id}": lunch.quantity for lunch in lunches}), 200

@app.route('/give_lunch', methods=['POST'])
@jwt_required()
def give_lunch():
    daily_lunch = TodayLunch.query.filter_by(student_id=Student.id).first()
    if not daily_lunch:
        return jsonify({'error': 'No lunch found for the user'}), 404

    lunch_id = daily_lunch.lunch_id
    db.session.delete(daily_lunch)

    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).first()
    if available_lunch:
        available_lunch.quantity += 1
    else:
        available_lunch = AvailableLunch(lunch_id=lunch_id, quantity=1)
        db.session.add(available_lunch)

    db.session.commit()
    return jsonify({'message': f'Lunch {lunch_id} given successfully'}), 200

@app.route('/request_lunch', methods=['POST'])
@jwt_required()
def request_lunch():
    data = request.get_json()
    lunch_id = data.get('lunch_id')
    if not lunch_id:
        return jsonify({'error': 'lunch_id is required'}), 400

    available_lunch = AvailableLunch.query.filter_by(lunch_id=lunch_id).with_for_update().first()
    if not available_lunch or available_lunch.quantity <= 0:
        return jsonify({'error': 'Requested lunch is not available'}), 404

    daily_lunch = TodayLunch.query.filter_by(student_id=Student.id).first()
    if daily_lunch:
        return jsonify({'error': 'Student already has a lunch assigned'}), 400

    available_lunch.quantity -= 1
    if available_lunch.quantity == 0:
        db.session.delete(available_lunch)

    new_daily_lunch = TodayLunch(student_id=Student.id, lunch_id=lunch_id)
    db.session.add(new_daily_lunch)

    db.session.commit()
    return jsonify({'message': f'Lunch {lunch_id} assigned to {Student.name} successfully'}), 200

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

# Start ngrok tunnel
public_url = ngrok.connect(addr="http://127.0.0.1:5000", domain="lamb-kind-preferably.ngrok-free.app")
print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")

if __name__ == '__main__':
    with app.app_context():
        pass

    app.run(debug=True, use_reloader=False)