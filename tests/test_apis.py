import app
import apis.common
import extensions

import json
from urllib.parse import urlencode
from contextlib import contextmanager
import uuid
import logging

import pytest


_DEFAULT_HEADERS = {'Content-Type': 'application/json',
                    'Accept': 'application/json'}


log = logging.getLogger(__name__)


@contextmanager
def user_set(client, user={'group': [apis.common.ADMIN_GROUP]}):
    with client.session_transaction() as sess:
        sess['user'] = user

    yield

    with client.session_transaction() as sess:
        sess.pop('user')


def _decode_response(result):
    """
    Decode a Response object, returning a tuple of its status code and
    JSON-decoded data.

    Returns a tuple of the response code and its decoded contents.
    """
    data = result.get_data(as_text=True)
    return result.status_code, json.loads(data) if data else None


def _get(client, path, **params):
    """
    Perform a GET request to client with the provided parameters.

    Returns a tuple of the response code and its decoded contents.
    """
    url = "{}?{}".format(path, urlencode(params)) if params else path
    log.info("GET:ing {}".format(url))

    return _decode_response(client.get(url, follow_redirects=True,
                                       headers=_DEFAULT_HEADERS))


def _put(client, resource, data):
    """
    Perform a PUT request to a client with the provided data.

    Returns a tuple of the response code and its decoded contents.
    """
    log.info("PUT:ing {} to {}".format(str(data), resource))

    return _decode_response(
        client.put(resource,
                   follow_redirects=True,
                   data=json.dumps(data),
                   headers=_DEFAULT_HEADERS))


def _delete(client, resource):
    """
    Perform a DELETE request to a client with the provided data.

    Returns a tuple of the response code and its decoded contents.
    """
    log.info("DELETE:ing {}".format(resource))

    return _decode_response(
        client.delete(resource,
                      follow_redirects=True,
                      headers=_DEFAULT_HEADERS))


@pytest.fixture(scope="function")
def client(request):
    """
    Fixture to set up a Flask test client
    """
    app.app.testing = True

    with app.app.test_client() as client:
        yield client

    log.info("App teardown initiated: re-initialising dummy backend")
    extensions.DummyStorage().init_app(app.app)


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_list_no_volumes(client, namespace):
    code, response = _get(client, "/{}/volumes".format(namespace))
    assert code == 200
    assert response == []


@pytest.mark.parametrize('volume_name,namespace',
                         zip(["samevolume"] * 4, ["ceph", "netapp"]))
def test_put_new_volume_idempotent(client, volume_name, namespace):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)
    with user_set(client):
        put_code, put_response = _put(client, resource, data={})

    assert put_code == 200
    assert not put_response

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name

    assert len(_get(client, '/{}/volumes'.format(namespace))[1]) == 1


@pytest.mark.parametrize('volume_name', ["firstvolume", "secondvolume"])
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_put_new_volume(client, volume_name, namespace):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        put_code, put_response = _put(client, resource, data={})

    assert put_code == 200
    assert not put_response

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name

    assert len(_get(client, '/{}/volumes'.format(namespace))[1]) == 1


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_get_nonexistent_volume(client, namespace):
    resource = '/{}/volumes/shouldnotexist'.format(namespace)

    get_code, get_response = _get(client, resource)

    print(get_response)

    assert get_code == 404

    assert 'message' in get_response


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_create_delete_volume(client, namespace):
    resource = '/{}/volumes/myvolume'.format(namespace)

    with user_set(client):
        _put(client, resource, data={})
        code, response = _delete(client, resource)

    assert code == 204

    get_code, _get_response = _get(client, resource)

    assert get_code == 404


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_create_delete_volume_unauthorised(client, namespace):
    resource = '/{}/volumes/myvolume'.format(namespace)

    put_code, _result = _put(client, resource, data={})
    assert put_code == 403

    get_code, _get_response = _get(client, resource)
    assert get_code == 404

    with user_set(client):
        put_code, _put_result = _put(client, resource, data={})

    delete_code, _result = _delete(client, resource)
    assert delete_code == 403
    final_get_code, _get_response = _get(client, resource)
    assert final_get_code == 200


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_create_wrong_group(client, namespace):
    resource = '/{}/volumes/wrong_group'.format(namespace)

    with user_set(client, user={'group': ['completely-unauthorised-group']}):
        put_code, _put_result = _put(client, resource, data={})

    assert put_code == 403
    get_code, _get_response = _get(client, resource)
    assert get_code == 404


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_delete_nonexistent_volume(client, namespace):
    resource = '/{}/volumes/{}'.format(namespace, uuid.uuid1())

    with user_set(client):
        delete_code, _result = _delete(client, resource)
    assert delete_code == 404


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_create_snapshot_from_volume(client, namespace):
    volume = '/{}/volumes/{}'.format(namespace, uuid.uuid1())

    with user_set(client):
        _put_code, _put_result = _put(client, volume,
                                      data={'max_autosize': 42,
                                            'autosize_increment': 12})

    snapshot_name = "{}".format("shotsnap", namespace)
    snapshot = '{}/snapshots/{}'.format(volume, snapshot_name)

    with user_set(client):
        snapshot_put_code, _snapshot_put_result = _put(client, snapshot, data={})

    assert snapshot_put_code == 201

    get_code, get_result = _get(client, snapshot)
    assert get_code == 200
    assert get_result['name'] == snapshot_name

    snapshots_get_code, get_results = _get(client, '{}/snapshots'.format(volume))
    assert snapshots_get_code == 200

    assert any(map(lambda x: x['name'] == snapshot_name, get_results))
    assert len(get_results) == 1


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_rollback_from_snapshot(client, namespace):
    volume = '/{}/volumes/{}'.format(namespace, uuid.uuid1())
