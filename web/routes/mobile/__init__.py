from flask import Blueprint

mobile_bp = Blueprint(
    'mobile',
    __name__,
    url_prefix='/mobile',
)

from web.routes.mobile import routes  # noqa: E402, F401
