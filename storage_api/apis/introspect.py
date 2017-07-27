import logging

from flask_restplus import Namespace, Resource
from flask import current_app

from .common.auth import USER_ROLES
from .common import auth
from .storage import exception_is_errorcode


api = Namespace('introspect',
                description='API configuration introspection')


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


@api.route('/subsystems')
class Subsystems(Resource):

    @api.doc(description="Get a list of all available subsystems")
    def get(self):
        return list(current_app.config['SUBSYSTEM'].keys())


@api.route('/role')
class Roles(Resource):

    @api.doc(description="Get a list of all available roles")
    def get(self):
        return USER_ROLES


@api.route('/role/<string:role>/egroups')
class RoleEgroups(Resource):

    @api.doc(description="Get a list of all egroups for a given role")
    def get(self, role):
        with exception_is_errorcode(api=api,
                                    exception=KeyError,
                                    error_code=404):
            return list(current_app.config['{}_GROUPS'.format(role)])


@api.route('/role/<string:role>/am_i_a')
class AmIA(Resource):

    @api.doc(description=("Returns True if the user is the given role,"
                          " False otherwise"))
    def get(self, role):
        role_content = getattr(auth, '{}_ROLE'.format(role))
        return auth.is_in_role(role_content)
