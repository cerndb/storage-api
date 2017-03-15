import json
from contextlib import contextmanager
import os

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

    def hard_delete_volume(self, volume_name):
        import netapp.api
        ONTAP_VSERVER = os.environ.get('ONTAP_VSERVER', 'vs1rac11')
        server_host = os.environ.get('ONTAP_HOST', 'db-51195')
        server_username = os.environ.get('ONTAP_USERNAME', "user-placeholder")
        server_password = os.environ.get('ONTAP_PASSWORD', "password-placeholder")
        s = netapp.api.Server(hostname=server_host, username=server_username,
                              password=server_password)

        with s.with_vserver(ONTAP_VSERVER):
            try:
                s.unmount_volume(volume_name)
                s.take_volume_offline(volume_name)
            finally:
                s.destroy_volume(volume_name)

    def login_session(self):
        login_url = self.get_server_url() + "/login"
        s = requests.Session()
        s.get(login_url)
        return s

    @contextmanager
    def perform(self, session, operation, relative_url, payload=None):
        result = getattr(session, operation)(
            self.get_server_url() + relative_url,
            headers=_DEFAULT_HEADERS,
            data=payload)
        try:
            yield result.json(), result.status_code
        except json.decoder.JSONDecodeError:
            yield None, result.status_code

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

        r1 = s.post(url + "/ceph/volumes/bork", data=json.dumps({}),
                    headers=_DEFAULT_HEADERS)
        assert r1.status_code == 200
        r = s.get(url + "/ceph/volumes/bork/locks")

        assert r.status_code == 200

    def test_netapp_get_volumes(self):
        url = self.get_server_url()
        s = self.login_session()
        r1 = s.get(url + "/netapp/volumes")
        assert r1.status_code == 200
        result = r1.json()
        assert result

    def test_netapp_get_specific_volume(self):
        url = self.get_server_url()
        s = self.login_session()

        NUM_COMPARISONS = 5

        for cmp_no, volume in enumerate(s.get(url + "/netapp/volumes").json()):
            by_name = s.get("{}/netapp/volumes/{}:{}"
                            .format(url, volume['filer_address'],
                                    volume['junction_path'])).json()
            print(volume)
            assert by_name == volume
            if cmp_no >= NUM_COMPARISONS:
                break

    def test_netapp_create_delete_volume(self):
        s = self.login_session()
        url = self.get_server_url()
        with self.perform(
                s, 'post',
                "/netapp/volumes/nothing:/test_volume_api_system_test_13",
                payload=json.dumps({'name': 'my_test_volume_api_system_test_13',
                                    'size_total': 20972})) as (r, code):

            try:
                assert code == 200
                all_names = [v['name'] for v in
                             s.get(url + "/netapp/volumes").json()]
                assert r['name'] in all_names

                r2 = s.delete(url + "/netapp/volumes/{}:{}".format(r['filer_address'],
                                                                   r['junction_path']),
                              headers=_DEFAULT_HEADERS)
                assert r2.status_code == 204

                assert r['name'] not in [v['name'] for v in
                                         s.get(url + "/netapp/volumes").json()]
            finally:
                self.hard_delete_volume(volume_name=r['name'])


    def test_openapi_spec_validity(self):
        url = self.get_server_url() + '/swagger.json'
        r = self.login_session().get(url)
        assert r.status_code == 200

        parsed_spec = r.json()
        assert isinstance(validator20.validate_spec(parsed_spec), RefResolver)
