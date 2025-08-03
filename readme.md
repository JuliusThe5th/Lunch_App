# Lunch Management System

This project is a Flask-based web application designed to manage student lunches. It allows administrators to upload lunch data, assign lunches to students, and track lunch history. The application integrates with Google OAuth for authentication and uses SQLAlchemy for database management.

## Features

- **Student Management**: Manage student data, including assigning unique card IDs.
- **Lunch Assignment**: Assign lunches to students and track their distribution.
- **PDF Upload**: Upload `.pdf` files to update lunch data.
- **Lunch History**: Export lunch history to an Excel file with timestamps.
- **Google OAuth Integration**: Authenticate users using Google Sign-In.
- **Real-Time Updates**: Use ngrok to expose the application for testing.

## Technologies Used

- **Backend**: Flask, Flask-SQLAlchemy, Flask-Migrate
- **Authentication**: Google OAuth (via Google ID token)
- **Database**: SQLite
- **File Handling**: Pandas for Excel file processing, pdfplumber for PDF parsing
- **Environment Management**: Python-dotenv
- **Tunneling**: Pyngrok

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Create a `.env` file in the project root.
   - Add the following variables:
     ```
     SQLALCHEMY_DATABASE_URI=sqlite:///lunch_app.db
     SECRET_KEY=<your-secret-key>
     GOOGLE_CLIENT_ID=<your-google-client-id>
     NGROK_AUTH_TOKEN=<your-ngrok-auth-token>
     UPLOAD_FOLDER=uploads
     FRONTEND_URL=http://localhost:5173
     ```

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

6. Start the application:
   ```bash
   python app.py
   ```

7. Access the application:
   - Local: `http://127.0.0.1:5000`
   - Ngrok: The public URL displayed in the terminal.

## API Endpoints

### 1. `/api/verify-token` (POST)
- **Description**: Authenticate user via Google OAuth token (ID token from Google Sign-In).
- **Request**:
  - Content-Type: `application/json`
  - Body:
    ```json
    {
      "fullName": "<full_name>",
      "picture": "<profile_picture_url>"
    }
    ```
- **Response**:
  - `200 OK`: Returns user info and JWT token (in cookie).
  - `400 Bad Request`: Invalid user data.

### 2. `/api/user-info` (GET)
- **Description**: Get authenticated user's info and lunch order.
- **Authentication**: Requires JWT token (sent in cookie).
- **Response**:
  - `200 OK`: JSON object with user info and lunch order (or null if none).
  - `401 Unauthorized`: Invalid or missing token.

### 3. `/upload` (POST)
- **Description**: Upload a PDF file containing lunch data for students.
- **Request**:
  - Multipart form-data with a `.pdf` file.
- **Response**:
  - `200 OK`: PDF processed and database updated.
  - `400/500`: Error details.

### 4. `/lunches` (GET)
- **Description**: Retrieve all available lunches and their quantities.
- **Response**:
  - `200 OK`: JSON object with lunch IDs and quantities.

### 5. `/give_lunch` (POST)
- **Description**: Mark a lunch as given to the authenticated student.
- **Authentication**: Requires JWT token.
- **Response**:
  - `200 OK`: Lunch given successfully.
  - `404 Not Found`: No lunch found for the user.

### 6. `/request_lunch` (POST)
- **Description**: Request a specific lunch for the authenticated student.
- **Authentication**: Requires JWT token.
- **Request**:
  - Content-Type: `application/json`
  - Body:
    ```json
    {
      "lunch_id": "<lunch_id>"
    }
    ```
- **Response**:
  - `200 OK`: Lunch assigned successfully.
  - `400 Bad Request`: Missing `lunch_id` or student already has a lunch.
  - `404 Not Found`: Requested lunch is not available.

### 7. `/lunch` (POST)
- **Description**: Mark lunch as given by card UID (for hardware integration).
- **Request**:
  - Content-Type: `application/json`
  - Body:
    ```json
    {
      "card_uid": "<hashed_card_uid>"
    }
    ```
- **Response**:
  - `200 OK`: Lunch given to student.
  - `404 Not Found`: Student or lunch not found.

### 8. `/assign_card` (POST)
- **Description**: Assign a card UID to a student.
- **Request**:
  - Content-Type: `application/json`
  - Body:
    ```json
    {
      "student_name": "<student_name>",
      "card_uid": "<card_uid>"
    }
    ```
- **Response**:
  - `200 OK`: Card assigned successfully.
  - `404 Not Found`: Student not found.
  - `400 Bad Request`: Card already assigned.

## Database Models

See `models.py` for details on:
- `Student`
- `TodayLunch`
- `AvailableLunch`
- `GivenLunch`

## Notes
- The backend expects Google authentication to be handled on the frontend, which sends the user's full name and profile picture to `/api/verify-token`.
- JWT tokens are set in cookies for secure authentication.
- PDF upload parses student lunch assignments and updates the database.
- Lunch history is exported to Excel before daily data is cleared.

## Development
- For frontend integration, set `FRONTEND_URL` in `.env` to match your frontend dev server.
- Use ngrok for public testing if needed.

## License
MIT
