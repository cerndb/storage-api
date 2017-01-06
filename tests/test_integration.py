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
    return result.status_code, json.loads(result.get_data(as_text=True))


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
    Perform a PUT request to a client with the provided data
    """
    return _decode_response(
        client.put(resource,
                   follow_redirects=True,
                   data=json.dumps(data),
                   headers=_DEFAULT_HEADERS))


@pytest.fixture(scope="function")
def client(request):
    """
    Fixture to set up a Flask test client
    """
    app.app.testing = True
    return app.app.test_client()


def test_list_no_volumes(client):
    code, response = _get(client, '/netapp/volumes')
    assert code == 200
    assert response == []


@pytest.mark.parametrize('volume_name', ["firstvolume", "secondvolume"])
def test_put_volume(client, volume_name):
    resource = '/netapp/volumes/{}'.format(volume_name)
    put_code, put_response = _put(client, resource, data={})

    assert put_code == 200
    assert not put_response

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name

    assert len(_get(client, '/netapp/volumes')[1]) >= 1
