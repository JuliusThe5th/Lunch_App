from flask import Blueprint, request, jsonify, redirect, url_for, session, render_template, current_app
from extensions import oauth, db
from models import Student
from itsdangerous import URLSafeSerializer, BadSignature

auth_bp = Blueprint('auth', __name__)

# ---------------------------------------------------------------------------
# Token helpers — sign/verify the user's email with the app's SECRET_KEY.
# The resulting token cannot be forged or tampered with by the client.
# ---------------------------------------------------------------------------

def _make_auth_token(email: str) -> str:
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(email)


def _read_auth_token(token: str):
    """Return the email embedded in *token*, or None if invalid/tampered."""
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    try:
        return s.loads(token)
    except BadSignature:
        return None


def _is_admin(email: str) -> bool:
    allowed = current_app.config.get('ALLOWED_ADMIN_EMAILS', [])
    return bool(email) and email in allowed

@auth_bp.route('/')
def index():
    return render_template('index.html')

@auth_bp.route('/dashboard', methods=['GET'])
def dashboard():
    token = request.args.get('token')
    if not token:
        return "Access token is missing", 400
    return render_template('dashboard.html', user=session.get('user'))

@auth_bp.route('/login', methods=['GET'])
def login():
    redirect_uri = url_for('auth.authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')

@auth_bp.route('/authorize')
def authorize():
    token = oauth.google.authorize_access_token()
    print(f"Access Token: {token}")
    user_info = oauth.google.get('userinfo').json()
    full_name = user_info.get('name')

    student = Student.query.filter_by(name=full_name).first()
    if not student:
        student = Student(name=full_name)
        db.session.add(student)
        db.session.commit()

    session['user'] = user_info
    session['access_token'] = token['access_token']

    # Redirect to dashboard with the token
    return redirect(url_for('auth.dashboard', token=token['access_token']))

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('access_token', None)
    return redirect(url_for('auth.index'))


# ---------------------------------------------------------------------------
# JSON API endpoints — used by the Vue SPA
# ---------------------------------------------------------------------------

@auth_bp.route('/api/verify-token', methods=['POST'])
def api_verify_token():
    """Validate a Google OAuth access token server-side and open a session.

    Expects JSON body: { "googleToken": "<Google access token>" }
    Returns: { token, name, email, picture, is_admin }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    google_access_token = data.get('googleToken')
    if not google_access_token:
        return jsonify({'error': 'googleToken required'}), 400

    try:
        user_info = oauth.google.get(
            'userinfo', token={'access_token': google_access_token}
        ).json()
        if 'error' in user_info:
            return jsonify({'error': 'Invalid token'}), 401
    except Exception:
        return jsonify({'error': 'Token validation failed'}), 401

    email = user_info.get('email')
    session.clear()
    session['user'] = user_info
    session['access_token'] = google_access_token

    return jsonify({
        'token': _make_auth_token(email),
        'name': user_info.get('name'),
        'email': email,
        'picture': user_info.get('picture'),
        'is_admin': _is_admin(email),
        'message': 'Authentication successful'
    })


@auth_bp.route('/api/user-info')
def api_user_info():
    """Return the current user's profile and admin status.

    Accepts a signed Bearer token (issued by /api/verify-token) via the
    Authorization header, falling back to the server-side session cookie.
    Admin status is always derived server-side — never trusted from the client.
    """
    email = None
    user_info = {}

    # Prefer the signed Bearer token so the SPA can call this without a cookie
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        email = _read_auth_token(auth_header.split(' ', 1)[1])

    # Fall back to session (server-rendered or socket-based flows)
    if not email and 'user' in session:
        user_info = session['user']
        email = user_info.get('email')

    if not email:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({
        'name': user_info.get('name', ''),
        'email': email,
        'picture': user_info.get('picture', ''),
        'is_admin': _is_admin(email),
    })


@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """Clear the server-side session (SPA logout endpoint)."""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})