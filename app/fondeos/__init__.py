from flask import Blueprint

fondeos = Blueprint('fondeos', __name__)

from . import routes  # noqa
