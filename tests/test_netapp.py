import app
import pytest
import json
from urllib.parse import urlencode


_DEFAULT_HEADERS = {'Content-Type': 'application/json',
                    'Accept': 'application/json'}


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
    return _decode_response(client.get(url, follow_redirects=True,
                                       headers=_DEFAULT_HEADERS))


def _put(client, resource, data):
    """
    Perform a PUT request to a client with the provided data.

    Returns a tuple of the response code and its decoded contents.
    """
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
    return app.app.test_client()


@pytest.mark.parametrize('namespace', ["ceph", "netapp"])
def test_list_no_volumes(client, namespace):
    code, response = _get(client, "/{}/volumes".format(namespace))
    assert code == 200
    assert response == []


@pytest.mark.parametrize('volume_name,namespace',
                         zip(["samevolume"] * 4, ["ceph", "netapp"]))
def test_put_new_volume_idempotent(client, volume_name, namespace):
    resource = '/{}/volumes/{}'.format(namespace, volume_name)
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
    put_code, put_response = _put(client, resource, data={})

    assert put_code == 200
    assert not put_response

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name

    assert len(_get(client, '/{}/volumes'.format(namespace))[1]) >= 1


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

    _put(client, resource, data={})

    code, response = _delete(client, resource)

    assert code == 204

    get_code, _get_response = _get(client, resource)

    assert get_code == 404
