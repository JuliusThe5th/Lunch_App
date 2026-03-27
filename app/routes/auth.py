from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required
from app.extensions import db
from app.models import Student
from app.services import split_name
from firebase_admin import auth as firebase_auth

bp = Blueprint('auth', __name__)


@bp.route('/verify-token', methods=['POST'])
def verify_token():
    """Verify Google OAuth token and create/login user"""
    user_data = request.json
    print(f"Received user data: {user_data}")
    try:
        id_token = request.json.get('token')

        if not id_token:
            return jsonify({'error': 'Missing ID token'}), 400

        # Ověření tokenu pomocí Firebase
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        full_name = decoded_token.get('name')
        picture = decoded_token.get('picture')

        if not full_name:
            return jsonify({'error': 'Invalid user data - missing name'}), 400

        student, error, status = split_name(full_name)

        if error:
            if status == 404:
                # Create new student
                name_parts = full_name.split(' ', 1)
                if len(name_parts) != 2:
                    return jsonify({'error': 'Invalid name format - need both first name and surname'}), 400

                first_name, surname = name_parts

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
                return jsonify(error), status

        # Create JWT token
        access_token = create_access_token(identity=full_name)

        response = jsonify({
            'message': 'Authentication successful',
            'name': full_name,
            'picture': picture,
            'is_admin': student.isAdmin,
        })

        response.set_cookie(
            'access_token_cookie',
            access_token,
            secure=False,
            httponly=False,
            samesite='Lax',
            domain=None,
            max_age=30 * 24 * 60 * 60
        )

        return response

    except firebase_auth.InvalidIdTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except firebase_auth.ExpiredIdTokenError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        print(f"Authentication error: {e}")
        return jsonify({'error': 'Authentication failed'}), 401

@bp.route('/logout', methods=['POST'])
def logout():
    """Clear JWT token cookie to log out user"""
    response = jsonify({'message': 'Successfully logged out'})

    response.delete_cookie(
        'access_token_cookie',
        secure=False,
        httponly=True,
        samesite='Lax'
    )

    return response, 200

