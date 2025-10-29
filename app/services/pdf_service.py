import os
import datetime
import pytz
import pandas as pd
import pdfplumber
import re
from app.extensions import db
from app.models import Student, TodayLunch, AvailableLunch, GivenLunch


def get_current_date_str():
    """Get current date in EU format (DD-MM-YYYY)"""
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
                student_count = Student.query.count()
                return student_count == 0
            return False

        last_lunch_date = last_given_lunch.timestamp.date()
        return current_date > last_lunch_date

    except Exception as e:
        print(f"Error checking database date: {e}")
        return False


def export_lunch_history(history_folder):
    """Export lunch history to an Excel file"""
    given_lunches = db.session.query(
        Student.name, GivenLunch.lunch_id, GivenLunch.timestamp
    ).join(Student, Student.id == GivenLunch.student_id) \
        .order_by(Student.name).all()

    print(f"Given lunches data: {given_lunches}")

    if given_lunches:
        data = [
            {
                'name': name,
                'lunch': lunch_id,
                'timestamp': timestamp.strftime('%H:%M:%S')
            }
            for name, lunch_id, timestamp in given_lunches
        ]
        df = pd.DataFrame(data)

        first_given_lunch = db.session.query(GivenLunch.timestamp).order_by(GivenLunch.timestamp).first()
        print(f"First given lunch timestamp: {first_given_lunch}")

        if first_given_lunch:
            date_str = first_given_lunch.timestamp.strftime('%d-%m-%Y')
            file_name = f"lunches {date_str}.xlsx"
            file_path = os.path.join(history_folder, file_name)

            print(f"Saving file to: {file_path}")
            df.to_excel(file_path, index=False)
        else:
            print("No given lunches found to export.")
    else:
        print("No given lunches data available.")


def clear_existing_data():
    """Clear existing lunch data from the database"""
    db.session.query(TodayLunch).delete()
    db.session.commit()

    db.session.query(AvailableLunch).delete()
    db.session.commit()

    db.session.query(GivenLunch).delete()
    db.session.commit()

    db.session.query(AvailableLunch).update({AvailableLunch.quantity: 0})
    db.session.commit()
    print("Existing data cleared from database")


def process_pdf(filepath, upload_folder):
    """Process uploaded PDF file and extract lunch data"""
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
                    for i, line in enumerate(lines):
                        if 'O1' in line and 'O2' in line and 'O3' in line:
                            header_found = True
                            header_line_idx = i
                            print(f"Found header line: {line}")
                            lines = lines[header_line_idx + 1:]
                            break

                if header_found:
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        match = re.match(r'([^\d]+)\s+([^\d]+)\s+([01])\s+([01])\s+([01])', line)
                        if match:
                            surname = match.group(1).strip()
                            first_name = match.group(2).strip()
                            lunch1, lunch2, lunch3 = match.group(3), match.group(4), match.group(5)

                            student = Student.query.filter_by(name=first_name, surname=surname).first()
                            if not student:
                                student = Student(name=first_name, surname=surname)
                                db.session.add(student)
                                db.session.commit()

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

    if not all_data:
        return None, page_data_counts

    # Process extracted data
    student_count = 0
    for item in all_data:
        student = Student.query.get(item["student_id"])
        if not student:
            continue

        existing_lunch = TodayLunch.query.filter_by(student_id=student.id).first()
        if existing_lunch:
            db.session.delete(existing_lunch)

        daily_lunch = TodayLunch(student_id=student.id, lunch_id=item["LunchNumber"])
        db.session.add(daily_lunch)
        student_count += 1

    db.session.commit()
    return student_count, page_data_counts

