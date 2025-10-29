from .auth import bp as auth_bp
from .lunch import bp as lunch_bp
from .admin import bp as admin_bp
from .students import bp as students_bp

__all__ = ['auth_bp', 'lunch_bp', 'admin_bp', 'students_bp']

