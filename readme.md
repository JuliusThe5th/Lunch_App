# Lunch Management System

This project is a Flask-based web application designed to manage student lunches. It allows students to authenticate via Google, request lunches, and administrators to upload lunch data through PDF files. The system includes features for tracking lunch history and facilitating lunch transfers between students.

## Features

- **Student Authentication**: Sign in with Google OAuth
- **Lunch Management**:
  - View assigned lunches
  - Request available lunches
  - Transfer lunches to other students
  - Return lunch to the available pool
- **Administrative Features**:
  - Upload PDF files with lunch assignments
  - Track lunch history
  - Export lunch history to Excel
- **Student Management**:
  - Automatic student creation on first login
  - Associate students with card IDs for physical lunch distribution
- **History Tracking**:
  - Automatically exports lunch data to Excel files
  - Maintains a record of given lunches

## Architecture

The application is split into:

- **Backend**: Flask-based REST API with JWT authentication
- **Frontend**: Vue.js single-page application
- **Database**: SQLite with SQLAlchemy ORM

## Technologies Used

- **Backend**:
  - Flask: Web framework
  - Flask-SQLAlchemy: ORM for database interaction
  - Flask-Migrate: Database migrations
  - Flask-JWT-Extended: JWT authentication
  - pdfplumber: PDF parsing
  - pandas: Data processing and Excel file generation
- **Frontend**:
  - Vue.js: Progressive JavaScript framework
  - Vue Router: Client-side routing
  - Pinia: State management
  - Vue3-Google-Login: Google authentication integration
- **Infrastructure**:
  - SQLite: Database
  - pyngrok: Tunneling for local development testing

## Installation

### Backend Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables by creating a `.env` file:
   ```
   SQLALCHEMY_DATABASE_URI=sqlite:///lunch_app.db
   SECRET_KEY=your-secret-key
   GOOGLE_CLIENT_ID=your-google-client-id
   NGROK_AUTH_TOKEN=your-ngrok-auth-token
   UPLOAD_FOLDER=uploads
   FRONTEND_URL=http://localhost:5173
   ```

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

6. Run the backend:
   ```bash
   flask run
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file with your Google Client ID:
   ```
   VITE_GOOGLE_CLIENT_ID=your-google-client-id
   VITE_API_BASE_URL=http://localhost:5000
   ```

4. Run the development server:
   ```bash
   npm run dev
   ```

## API Endpoints

### Authentication

#### `/api/verify-token` (POST)
- Authenticates user via Google Sign-In data
- Request body: `{ fullName: string, picture: string }`
- Response: Sets JWT cookie and returns user info

#### `/api/logout` (POST)
- Clears the JWT cookie to log out the user
- Response: Success message

#### `/api/user-info` (GET)
- Returns the authenticated user's information and lunch status
- Requires JWT authentication
- Response: User name and lunch details

### Lunch Management

#### `/api/lunches` (GET)
- Returns all available lunches and their quantities
- Response: Object with lunch IDs as keys and quantities as values

#### `/api/request_lunch` (POST)
- Requests a specific lunch for the authenticated student
- Requires JWT authentication
- Request body: `{ lunch_id: string }`
- Response: Success message or error

#### `/api/give_lunch` (POST)
- Returns the authenticated student's lunch to the available pool
- Requires JWT authentication
- Response: Success message or error

#### `/api/give_lunch_direct` (POST)
- Transfers lunch from authenticated student to another student
- Requires JWT authentication
- Request body: `{ student_id: string }`
- Response: Success message with details of transfer

### Student Management

#### `/api/students` (GET)
- Returns list of students who don't have lunch assigned
- Requires JWT authentication
- Response: Array of student objects with IDs, names, and pictures

### Administrative Endpoints

#### `/upload` (POST)
- Uploads a PDF file containing lunch data
- Request: Multipart form with PDF file
- Response: Details of processed data

#### `/lunch` (POST)
- Marks lunch as given using card UID (for hardware integration)
- Request body: `{ card_uid: string }`
- Response: Success message or error

## Database Models

### Student
- Properties: id, name, surname, pictureURL, card_id

### AvailableLunch
- Properties: lunch_id, quantity

### TodayLunch
- Properties: id, student_id, lunch_id
- Relationships: student, lunch

### GivenLunch
- Properties: id, student_id, lunch_id, timestamp
- Relationships: student, lunch

## Development Workflow

1. Students authenticate with Google
2. Students can view their assigned lunch or request an available one
3. Students can transfer lunches to others who don't have one
4. Administrators upload PDF files to update lunch assignments
5. The system automatically tracks lunch history and exports it to Excel files

## Troubleshooting

- JWT authentication issues: Check cookie settings and CORS configuration
- Database migration errors: Check constraint names in migration files
- PDF parsing issues: Verify the PDF format matches the expected structure
