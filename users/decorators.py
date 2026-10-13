from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Usage: @role_required("PME")  ou  @role_required("PME", "ADMIN")"""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied          # page 403
            return view(request, *args, **kwargs)
        return wrapper
    return decorator