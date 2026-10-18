from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def rol_requerido(*roles):
    """Permite la vista solo a usuarios con alguno de los roles indicados."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(*args, **kwargs):
            if current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador
