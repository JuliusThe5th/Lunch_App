# Lunch Management System

A full-stack web application for managing student lunch assignments. Students authenticate via Firebase/Google, manage their lunch preferences, and transfer lunches between peers. Administrators upload PDF files to assign lunches and track distribution via card IDs.

## Features

- **Student Authentication**: Firebase Google Sign-In with automatic account creation
- **Lunch Management**:
  - View assigned lunches for today
  - Request available lunches from pool
  - Transfer lunches directly to other students
  - Return unused lunch to available pool
  - Real-time lunch availability updates via WebSockets
- **Administrative Features**:
  - PDF upload for bulk lunch assignments (parses lunch data and assigns to students)
  - Mark lunches as given via card ID scanning
  - Track lunch distribution history
  - Export lunch history to Excel
- **Student Management**:
  - Automatic student creation on first login
  - Link physical card IDs for cafeteria distribution
  - Support for admin role assignment
- **History Tracking**:
  - Records all lunch transfers and distributions
  - Maintains daily lunch history with timestamps
  - Automatic database reset at day boundary

## Architecture

The application follows a client-server architecture with real-time communication:

- **Backend**: Flask REST API with JWT authentication and WebSocket support
- **Frontend**: Vue.js 3 single-page application with Pinia state management
- **Authentication**: Firebase Admin SDK on backend, Firebase JS SDK on frontend
- **Real-time**: Flask-SocketIO for bi-directional communication (lunch updates, user status)
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: PDF parsing for lunch assignments, Excel export for history

## Technologies Used

- **Backend**:
  - Flask: Web framework
  - Flask-SocketIO: WebSocket support for real-time updates
  - Flask-SQLAlchemy: ORM for database interaction
  - Flask-Migrate: Database migrations with Alembic
  - Flask-JWT-Extended: JWT authentication and authorization
  - Flask-CORS: Cross-Origin Resource Sharing
  - firebase-admin: Firebase authentication and management
  - pdfplumber: PDF parsing and extraction
  - pandas: Data processing and Excel export
  - pyngrok: Tunneling for development (NGROK integration)
- **Frontend**:
  - Vue.js 3: Progressive JavaScript framework
  - Vue Router: Client-side routing
  - Pinia: State management
  - Firebase JS SDK: Google Sign-In and authentication
- **Database**: SQLite with SQLAlchemy ORM and Alembic migrations
- **External Services**: Firebase Authentication, Google OAuth 2.0

## Installation

### Prerequisites

- Python 3.8+ and pip
- Node.js 16+ and npm
- Firebase project with Google Sign-In enabled
- Google OAuth 2.0 credentials

### Backend Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Lunch_App
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # source .venv/bin/activate  # On macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables in `.env`:
   ```
   FLASK_ENV=development
   FLASK_APP=run.py
   SECRET_KEY=your-secret-key-here
   SQLALCHEMY_DATABASE_URI=sqlite:///lunch_app.db
   UPLOAD_FOLDER=uploads
   FRONTEND_URL=http://localhost:5173
   
   # Firebase configuration (download from Firebase Console)
   GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
   
   # Gmail service (optional, for PDF email processing)
   LUNCH_PROVIDER_EMAIL=lunch@example.com
   
   # ngrok tunneling (optional, for development)
   NGROK_AUTH_TOKEN=your-ngrok-token
   ```

5. Initialize database:
   ```bash
   flask db upgrade
   ```

6. Run backend server (with WebSocket support):
   ```bash
   python run.py
   # or use the batch file:
   start_server.bat
   ```
   Server runs on `http://127.0.0.1:5000`

### Frontend Setup

1. Navigate to frontend directory (if separate):
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create `.env` file:
   ```
   VITE_GOOGLE_CLIENT_ID=your-google-client-id
   VITE_API_BASE_URL=http://localhost:5000
   ```

4. Run development server:
   ```bash
   npm run dev
   ```
   Frontend runs on `http://localhost:5173` (default Vite port)

3. Create a `.env` file with your Google Client ID:
   ```
   VITE_GOOGLE_CLIENT_ID=your-google-client-id
   VITE_API_BASE_URL=http://localhost:5000
   ```

4. Run the development server:
   ```bash
   npm run dev
   ```

## API Reference

### REST Endpoints

#### Authentication

**POST `/api/verify-token`**
- Verifies Firebase ID token and creates/updates student record
- Request: `{ "token": "<firebase_id_token>" }`
- Response: JWT cookie + user info with `{ "name", "picture", "is_admin" }`

**POST `/api/logout`**
- Clears JWT cookie and logs out user
- Response: Success message

#### Lunch Management (Protected Routes - Require JWT)

**POST `/api/request_lunch`**
- Student requests a lunch from available pool
- Request: `{ "lunch_id": number }`
- Response: Confirmation message or error if lunch unavailable/student already has lunch

**POST `/api/give_lunch`**
- Returns student's current lunch to available pool
- Response: Success message with lunch_id

**POST `/api/give_lunch_direct`**
- Transfers lunch from authenticated student to another student
- Request: `{ "student_id": number }`
- Response: Transfer details (sender, recipient, lunch_id) or error if recipient already has lunch

#### Admin Endpoints (Protected - Require Admin Role)

**POST `/api/upload`**
- Upload PDF file with lunch assignments
- Request: Multipart form-data with PDF file
- Response: Processing results `{ "emails_processed", "pdfs_processed", "total_students_added", "errors" }`

**POST `/api/lunch`** (Card Scanner Integration)
- Mark lunch as given using student card ID/UID
- Request: `{ "card_uid": string }`
- Response: Student and lunch confirmation or error

### WebSocket Events (Socket.IO)

Connect with JWT token:
```javascript
io('http://localhost:5000', { auth: { token: jwtToken } })
```

**Client → Server Events:**

- `get_user_info` - Fetch authenticated user's lunch status and details
- `get_students` - Get students without lunch assigned (available recipients)
- `get_all_students` - Get all students with their lunch status
- `get_available_lunches` - Get lunch availability (lunch_id: quantity)

**Server → Client Broadcasts:**

- `user_info_update` - Updates when user's lunch status changes
- `lunch_updates` - Broadcasts when lunch pool availability changes
- `students_update` - Broadcasts when student lunch assignments change

## Database Models

All models use SQLAlchemy ORM with SQLite backend.

### Student
- `id`: Integer (Primary Key)
- `name`: String (Required) - First name
- `surname`: String (Required) - Last name
- `pictureURL`: String - Google profile picture URL
- `card_id`: String (Unique) - Physical card ID for cafeteria scanning
- `isAdmin`: Boolean (default: False) - Admin privilege flag
- **Relations**: `today_lunch` (one-to-one), `given_lunches` (one-to-many)

### TodayLunch
- `id`: Integer (Primary Key)
- `student_id`: Integer (Foreign Key) - Links to Student
- `lunch_id`: Integer - Type of lunch assigned
- **Relations**: `student` (many-to-one)
- **Purpose**: Current lunch assignment for today (one per student maximum)

### AvailableLunch
- `lunch_id`: Integer (Primary Key) - Type of lunch
- `quantity`: Integer - Number of available portions
- **Purpose**: Lunch pool tracking for student requests

### GivenLunch
- `id`: Integer (Primary Key)
- `student_id`: Integer (Foreign Key) - Links to Student
- `lunch_id`: Integer - Type of lunch given
- `timestamp`: DateTime - When lunch was distributed
- **Relations**: `student` (many-to-one)
- **Purpose**: Historical record of all lunch distributions

## Development Workflow

### User Journey

1. **Student Authentication**
   - Student clicks "Login with Google"
   - Firebase SDK opens Google OAuth popup
   - Firebase validates and returns ID token
   - Backend verifies token and creates/updates Student record
   - JWT cookie issued for subsequent requests

2. **Daily Workflow**
   - Admin uploads PDF with lunch assignments → processes and creates `TodayLunch` records
   - Students view assigned lunch or request from available pool (managed in `AvailableLunch`)
   - Students can transfer their lunch to peers or return to pool
   - Admin/Cafeteria staff mark lunch as given via card scanner → records in `GivenLunch`

3. **End of Day**
   - Lunch history exported to Excel
   - Database automatically clears when new day starts (if new lunch data provided)

### Database State Management

- **New Day**: When PDF uploaded with new lunch data, system checks if date changed. If so, clears `TodayLunch` and `AvailableLunch` tables
- **Real-time Sync**: Socket.IO broadcasts all state changes to connected clients
- **Idempotency**: Lunch transfers validate current state to prevent double-assignment

## Troubleshooting

### Authentication Issues

**Error: "Invalid user identity" or JWT validation fails**
- Verify Firebase Admin SDK credentials in `serviceAccountKey.json`
- Check `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to correct file
- Ensure Firebase project has Google Sign-In enabled

**Error: CORS issues with frontend**
- Verify `FRONTEND_URL` environment variable matches frontend origin
- Check Flask-CORS is configured correctly in `app/__init__.py`
- WebSocket connection requires same origin as REST API

### WebSocket Connection Issues

**Error: WebSocket connection fails or times out**
- Verify SocketIO is initialized in Flask app
- Check client connects with proper JWT: `io(url, { auth: { token: jwtToken } })`
- For development: WebSockets may need special configuration in firewalls/proxies

**Events not received:**
- Verify client joined correct room (user should join `lunch_updates` and `user_{identity}`)
- Check browser console for SocketIO errors
- Verify backend has `socketio.emit()` in proper namespace

### Database Issues

**Error: "column 'lunch_id' does not exist"**
- Run migrations: `flask db upgrade`
- Check that all migration files are present in `migrations/versions/`
- Delete `lunch_app.db` and re-run `flask db upgrade` to reset

**Error: Constraint violations (foreign keys, unique keys)**
- Verify `card_id` is unique if setting it manually
- Ensure student records exist before assigning `TodayLunch` entries
- Check migration names in constraint error messages against `migrations/versions/`

### PDF Upload Issues

**Error: PDF parsing fails or data not extracted**
- Verify PDF format matches expected structure (check `pdf_service.py`)
- Test with sample PDF included in project documentation
- Check `pdfplumber` version compatibility

**Error: "Failed to create student"**
- Verify name format in PDF is "FirstName Surname" (two parts)
- Check database has no duplicate students with same name/surname
- Review admin user privileges

### Performance Issues

**Lunch transfers slow or WebSocket lag**
- Check database indices on frequently-queried columns (student_id, lunch_id)
- Monitor Flask debug mode overhead (`--no-debug` for production)
- Consider connection pooling if many concurrent users

## Project Structure

```
Lunch_App/
├── app/                          # Main Flask application package
│   ├── __init__.py              # App factory (create_app)
│   ├── config.py                # Configuration for different environments
│   ├── extensions.py            # Flask extensions setup (db, jwt, cors, socketio)
│   ├── socketio_handlers.py     # WebSocket event handlers
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── student.py
│   │   ├── today_lunch.py
│   │   ├── available_lunch.py
│   │   └── given_lunch.py
│   ├── routes/                  # Blueprint definitions for REST endpoints
│   │   ├── auth.py             # Authentication routes
│   │   ├── lunch.py            # Lunch management routes
│   │   ├── admin.py            # Admin routes (PDF upload, card scanning)
│   │   └── students.py         # Student listing routes
│   └── services/                # Business logic services
│       ├── lunch_service.py    # Core lunch operations (transfer, pool, request)
│       └── pdf_service.py      # PDF parsing and lunch data processing
├── migrations/                  # Database migrations (Alembic)
├── scripts/                     # Utility scripts
│   └── czech_lunch_scraper.py  # Optional: scrape lunch data from websites
├── uploads/                     # PDF upload directory
├── instance/                    # Flask instance folder (DB file)
├── run.py                      # Entry point - starts Flask-SocketIO server
├── requirements.txt            # Python dependencies
├── start.bat / start_server.bat # Windows startup scripts
└── readme.md                   # This file
```

## Common Commands

### Development

```bash
# Start the backend with WebSocket support
python run.py
# or via batch file:
start_server.bat

# Run database migrations
flask db upgrade

# Create a new migration after model changes
flask db migrate -m "Description of changes"

# Reset database to empty state
flask db downgrade base
flask db upgrade

# Access Python shell with app context
python
>>> from flask import create_app
>>> from app.extensions import db
>>> app = create_app()
>>> with app.app_context():
...     # Query database, test services, etc.
...     pass

# Run frontend development server
cd frontend
npm run dev
```

### Testing & Debugging

```bash
# Enable Flask debug mode for development
set FLASK_ENV=development
set FLASK_DEBUG=1
python run.py

# Check ngrok tunnel status (if using remote access)
python -c "from pyngrok import ngrok; print(ngrok.get_tunnels())"

# Restart ngrok tunnel
python -c "from pyngrok import ngrok; ngrok.disconnect_all(); print('Tunnels reset')"
```

### Data Management

```bash
# Export lunch history to Excel (via API endpoint)
# Admin user can POST to /api/upload-pdf to trigger export

# Clear lunch data for new day (automatic on PDF upload with new date)
# Or manually:
sqlite3 instance/lunch_app.db "DELETE FROM today_lunch; DELETE FROM available_lunches;"
```

## Key Design Patterns

### Authentication & Authorization

- **JWT Cookies**: Stateless authentication via HTTP-only cookies (30-day expiry)
- **Admin Decorator**: `@admin_required` decorator on admin routes checks `Student.isAdmin` flag
- **Firebase Verification**: Backend always verifies ID tokens server-side, never trusts client claims

### Real-time Communication

- **Socket.IO Rooms**: 
  - `lunch_updates` - All updates broadcast to this room
  - `user_{identity}` - Personal updates sent to individual user
- **Broadcasting Pattern**: Services emit socket events after DB commits to ensure consistency

### Data Consistency

- **Transaction Pattern**: Database changes wrapped in try/except with rollback on error
- **Optimistic Locking**: `with_for_update()` used on critical lunch availability queries
- **Cascade Deletes**: Soft references between models prevent orphaned records

### PDF Processing

- **Bulk Operations**: PDF parsing extracts all lunch data before DB commit
- **Idempotent Processing**: Re-uploading same PDF day clears old assignments first
- **Error Collection**: All errors aggregated and returned instead of failing on first error

## Environment Variables

Key variables for `.env` file:

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLASK_ENV` | Environment (development/production) | `development` |
| `SECRET_KEY` | Session encryption key | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SQLALCHEMY_DATABASE_URI` | Database connection string | `sqlite:///lunch_app.db` |
| `FRONTEND_URL` | Frontend origin for CORS | `http://localhost:5173` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Admin SDK credentials file | `serviceAccountKey.json` |
| `UPLOAD_FOLDER` | PDF upload directory | `uploads` |
| `NGROK_AUTH_TOKEN` | Optional: ngrok tunneling token | From https://dashboard.ngrok.com |

## License

[Specify your license here]

## Support

For issues and questions, please open an issue in the repository or contact the development team.

