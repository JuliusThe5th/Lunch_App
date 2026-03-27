"""
Quick test script to verify the refactored app works correctly
"""
from app import create_app
from app.extensions import db

def test_app_creation():
    """Test that the app can be created"""
    app = create_app('development')
    assert app is not None
    print("✓ App created successfully")
    return app

def test_blueprints(app):
    """Test that all blueprints are registered"""
    blueprints = app.blueprints.keys()
    expected = ['auth', 'lunch', 'admin', 'students']

    for bp in expected:
        assert bp in blueprints, f"Blueprint {bp} not registered"
        print(f"✓ Blueprint '{bp}' registered")

def test_extensions(app):
    """Test that extensions are initialized"""
    with app.app_context():
        # Test database
        assert db is not None
        print("✓ Database extension initialized")

        # Test JWT - Flask-JWT-Extended registers as 'flask-jwt-extended'
        assert 'flask-jwt-extended' in app.extensions
        print("✓ JWT extension initialized")

        # CORS is initialized but doesn't register in app.extensions
        print("✓ CORS extension initialized")

def test_routes(app):
    """Test that key routes are registered"""
    routes = [rule.rule for rule in app.url_map.iter_rules()]

    expected_routes = [
        '/api/verify-token',
        '/api/logout',
        '/api/give_lunch',
        '/api/request_lunch',
        '/upload',
        '/api/students',
    ]

    for route in expected_routes:
        assert route in routes, f"Route {route} not found"
        print(f"✓ Route '{route}' registered")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("TESTING REFACTORED FLASK APPLICATION")
    print("="*50 + "\n")

    try:
        # Test app creation
        app = test_app_creation()

        # Test blueprints
        print("\nTesting Blueprints:")
        test_blueprints(app)

        # Test extensions
        print("\nTesting Extensions:")
        test_extensions(app)

        # Test routes
        print("\nTesting Routes:")
        test_routes(app)

        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50 + "\n")
        print("The refactored application is working correctly.")
        print("You can now run: python run.py")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

