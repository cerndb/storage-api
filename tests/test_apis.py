import app
import apis.common
import extensions

import json
from urllib.parse import urlencode
from contextlib import contextmanager
import uuid
import logging

import pytest
from hypothesis import given, example
from hypothesis.strategies import (characters, text, lists,
                                   composite, integers,
                                   booleans, sampled_from)


_DEFAULT_HEADERS = {'Content-Type': 'application/json',
                    'Accept': 'application/json'}


log = logging.getLogger(__name__)


def name_strings():
    """
    A Hypothesis strategy to generate reasonable name strings
    """
    def sane_first_character(s):
        c = s[0]
        return c not in ['/']

    bad_chars = ['\n', '#', '?', '%']

    return text(alphabet=characters(blacklist_characters=bad_chars,
                                    max_codepoint=1000),
                min_size=1).filter(sane_first_character)


@composite
def slash_names(draw):
    """
    A Compound Hypothesis strategy to generate names containing a / (not
    as the first character).
    """
    left = draw(name_strings())
    right = draw(name_strings())
    return "{}/{}".format(left, right)


@composite
def patch_arguments(draw):
    keys = draw(lists(elements=sampled_from(["autosize_enabled",
                                             "autosize_increment",
                                             "max_autosize"])))

    d = dict()

    for key in keys:
        if key == "autosize_enabled":
            d[key] = draw(booleans())
        else:
            d[key] = draw(integers(min_value=0))

    return d


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


def _put(client, resource, data={}):
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


def _patch(client, resource, data):
    """
    Perform a PATCH request to a client with the provided data.

    Returns a tuple of the response code and its decoded contents.
    """
    encoded_data = json.dumps(data)

    log.info("PATCH:ing {} with {}".format(resource, encoded_data))

    return _decode_response(
        client.patch(resource,
                     follow_redirects=True,
                     data=encoded_data,
                     headers=_DEFAULT_HEADERS))


@pytest.fixture(scope="function")
def client(request):
    """
    Fixture to set up a Flask test client
    """
    app.app.testing = True
    extensions.DummyStorage().init_app(app.app)

    backends = extensions.storage.StorageBackend.__subclasses__()

    for name, be in app.app.extensions.items():
        if be.__class__ in backends:
            # Re-wire all storage types to use the dummy back-end
            log.debug("Set storage back-end {} to use DummyStorage"
                      .format(name))
            app.app.extensions[name] = app.app.extensions['DummyStorage']

    with app.app.test_client() as client:
        yield client

    log.debug("App teardown initiated: re-initialising dummy backend")
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


@given(volume_name=name_strings())
@example(volume_name="foo/bar")
@example(volume_name="foo\\bar")
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_put_new_volume(client, namespace, volume_name):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        put_code, put_response = _put(client, resource, data={})

    assert put_code == 200
    assert not put_response

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name


@given(volume_name=name_strings())
@example(volume_name="foo/bar")
@example(volume_name="foo\\bar")
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_get_nonexistent_volume(client, namespace, volume_name):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)

    get_code, get_response = _get(client, resource)
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


@given(volume_name=name_strings())
@example(volume_name="foo/bar")
@example(volume_name="foo\\bar")
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_delete_nonexistent_volume(client, namespace, volume_name):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)

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

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _put(client, volume, data={})
        _put(client, snapshot_resource, data={})
        put_code, put_result = _put(client,
                                    volume,
                                    data={'from_snapshot': snapshot_name})

    assert put_code == 200
    # No way of verifying that the volume was actually restored.


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_clone_from_snapshot(client, namespace):
    master_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, master_name)
    clone_volume = '{}/volumes/{}'.format(namespace, "clone")

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _put(client, volume, data={})
        _put(client, snapshot_resource, data={})
        put_code, put_result = _put(client,
                                    clone_volume,
                                    data={'from_snapshot': snapshot_name,
                                          'from_volume': master_name})

    assert put_code == 201
    assert _get(client, clone_volume) == _get(client, volume)


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_clone_from_snapshot_name_collission(client, namespace):
    volume_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _put(client, volume, data={})
        _put(client, snapshot_resource, data={})
        put_code, put_result = _put(client,
                                    volume,
                                    data={'from_snapshot': snapshot_name,
                                          'from_volume': volume_name})
    assert put_code == 400
    assert 'message' in put_result
    assert 'in use' in put_result['message']


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_clone_from_snapshot_source_does_not_exist(client, namespace):
    volume_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        put_code, put_result = _put(client,
                                    volume,
                                    data={'from_snapshot': 'no-snapshot',
                                          'from_volume': volume_name})
    assert put_code == 404
    assert 'message' in put_result
    assert 'does not exist' in put_result['message']


@given(volume_name=name_strings(), patch_args=patch_arguments())
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_patch_volume(client, namespace, volume_name, patch_args):
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        put_code, put_result = _put(client, volume)

        patch_code, _patch_result = _patch(client, volume, data=patch_args)

    if patch_args:
        assert patch_code == 200
    else:
        assert patch_code == 400

    _get_code, get_result = _get(client, volume)

    for key, value in patch_args.items():
        assert get_result[key] == value


@given(volume_name=name_strings(), patch_args=patch_arguments())
@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_patch_nonexistent_volume(client, namespace, volume_name):
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        patch_code, _patch_result = _patch(client,
                                           volume,
                                           data={"autosize_enabled": True})

    assert patch_code == 404
