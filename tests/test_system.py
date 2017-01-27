import json

import requests
from flask_testing import LiveServerTestCase

from jsonschema import RefResolver
from swagger_spec_validator import validator20


_DEFAULT_HEADERS = {'Content-Type': 'application/json',
                    'Accept': 'application/json'}


class LiveTests(LiveServerTestCase):

    def create_app(self):
        from app import app
        app.config['TESTING'] = True
        app.config['LIVESERVER_PORT'] = 8943
        app.config['LIVESERVER_TIMEOUT'] = 10
        app.debug = True
        return app

    def login_session(self):
        login_url = self.get_server_url()  + "/login"
        s = requests.Session()
        s.get(login_url)
        return s

    def test_server_root_ok(self):
        url = self.get_server_url()
        r = requests.get(url + "/")
        assert r.status_code == 200

    def test_login(self):
        url = self.get_server_url()
        r = requests.get(url + "/login")
        assert r.status_code == 200

    def test_login_logout(self):
        url = self.get_server_url()
        s = self.login_session()
        r = s.get(url + "/logout")
        assert r.status_code == 200

    def test_get_protected_resource(self):
        url = self.get_server_url()
        s = self.login_session()

        r1 = s.put(url + "/ceph/volumes/bork", data=json.dumps({}),
                   headers=_DEFAULT_HEADERS)
        assert r1.status_code == 200
        r = s.get(url + "/ceph/volumes/bork/locks")
        assert r.status_code == 200

    def test_openapi_spec_validity(self):
        url = self.get_server_url() + '/swagger.json'
        r = self.login_session().get(url)
        assert r.status_code == 200

        parsed_spec = r.json()
        assert isinstance(validator20.validate_spec(parsed_spec), RefResolver)
