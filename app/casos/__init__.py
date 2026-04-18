from flask import Blueprint

casos = Blueprint('casos', __name__)

from . import routes  # noqa
