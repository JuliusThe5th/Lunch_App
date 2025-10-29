import os
import click
from pyngrok import ngrok
from app import create_app
from app.extensions import db, socketio

# Create the Flask app
app = create_app()


@app.cli.command()
@click.option('--host', default='127.0.0.1', help='The interface to bind to.')
@click.option('--port', default=5000, help='The port to bind to.')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode.')
def run_socketio(host, port, debug):
    """Run the Flask-SocketIO development server.

    This is the proper way to run the app with Socket.IO support.
    Use this instead of 'flask run' which doesn't support WebSockets.

    Usage:
        flask run-socketio
        flask run-socketio --port 8080
        flask run-socketio --no-debug
    """
    print("="*50)
    print("Starting Flask-SocketIO server...")
    print(f"Server: http://{host}:{port}")
    print("Press CTRL+C to quit")
    print("="*50)

    # Ensure DB tables exist
    with app.app_context():
        try:
            db.create_all()
            print("✓ Database tables ensured.")
        except Exception as e:
            print(f"✗ db.create_all failed: {e}")

    # Start ngrok if enabled
    if os.getenv('ENABLE_NGROK') == '1':
        try:
            public_url = ngrok.connect(
                addr=f"http://{host}:{port}",
                domain="lamb-kind-preferably.ngrok-free.app"
            )
            print(f'✓ ngrok tunnel "{public_url}" -> "http://{host}:{port}"')
        except Exception as e:
            print(f"✗ Ngrok start skipped/failed: {e}")

    print("\n" + "="*50)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    # Ensure DB tables exist for dev (prevents "no such table" errors)
    with app.app_context():
        try:
            db.create_all()
            print("Database tables ensured.")
        except Exception as e:
            print(f"db.create_all failed: {e}")

    # Start ngrok only when explicitly enabled (optional feature)
    if os.getenv('ENABLE_NGROK') == '1':
        try:
            public_url = ngrok.connect(
                addr="http://127.0.0.1:5000",
                domain="lamb-kind-preferably.ngrok-free.app"
            )
            print(f' * ngrok tunnel "{public_url}" -> "http://127.0.0.1:5000"')
        except Exception as e:
            print(f"Ngrok start skipped/failed: {e}")

    # Always start with SocketIO (ngrok is optional)
    print("Starting Flask-SocketIO server...")
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)

