import app
import apis.common
import extensions
from utils import compose_decorators

import json
from urllib.parse import urlencode
from contextlib import contextmanager
import uuid
import logging
from functools import partial

import pytest
from hypothesis import given
from hypothesis.strategies import (characters, text, lists,
                                   composite, integers,
                                   booleans, sampled_from)


_DEFAULT_HEADERS = {'Content-Type': 'application/json',
                    'Accept': 'application/json'}

log = logging.getLogger(__name__)


def nice_strings(bad_chars):
    """
    A Hypothesis strategy to generate reasonable name strings
    """
    def sane_first_character(s):
        c = s[0]
        return c not in ['/']

    return text(alphabet=characters(blacklist_characters=bad_chars,
                                    max_codepoint=1000),
                min_size=1).filter(sane_first_character)


name_strings = partial(nice_strings, bad_chars=['\n', '#', '?', '%'])
policy_name_strings = partial(nice_strings, bad_chars=['\n', '/', '?', '#', '%'])

# Useful parameterisations:
params_namespaces = pytest.mark.parametrize('namespace', ["ceph", "netapp"])
params_vol_presence = pytest.mark.parametrize('vol_exists',
                                              ["vol_present", "vol_absent"])
params_policy_presence = pytest.mark.parametrize(
    'policy_status',
    ["policy_present", "policy_absent"])
params_auth_status = pytest.mark.parametrize('auth',
                                             ["authorised", "not_authorised"])


params_volume_names = compose_decorators(given(volume_name=name_strings()))
params_vol_ns_auth = compose_decorators(params_volume_names,
                                        params_namespaces,
                                        params_auth_status,
                                        params_vol_presence)
params_ns_auth = compose_decorators(params_namespaces,
                                    params_auth_status)


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


def _open(client, path, method, data={}, **params):
    url = "{}?{}".format(path, urlencode(params)) if params else path

    log.info("{}:ing to {} with data: {}".format(method, url, str(data)))

    return _decode_response(client.open(path=url,
                                        method=method,
                                        follow_redirects=True,
                                        data=json.dumps(data),
                                        headers=_DEFAULT_HEADERS))


_get = partial(_open, method="GET")
_put = partial(_open, method="PUT")
_post = partial(_open, method="POST")
_delete = partial(_open, method="DELETE")
_patch = partial(_open, method="PATCH")


@pytest.fixture(scope="function")
def client(request):
    """
    Fixture to set up a Flask test client
    """
    app.app.testing = True
    extensions.DummyStorage().init_app(app.app)

    backend_classes = extensions.storage.StorageBackend.__subclasses__()

    for name, be in app.app.extensions.items():
        if be.__class__ in backend_classes:
            # Re-wire all storage types to use the dummy back-end
            log.debug("Set storage back-end {} to use DummyStorage"
                      .format(name))
            app.app.extensions[name] = app.app.extensions['DummyStorage']

    with app.app.test_client() as client:
        yield client

    log.debug("App teardown initiated: re-initialising dummy backend")
    extensions.DummyStorage().init_app(app.app)


def init_vols_from_params(client, namespace, auth, vol_exists, volume_name):
    volume_resource = '/{}/volumes/{}'.format(namespace, volume_name)
    authorised = auth == "authorised"
    volume_exists = vol_exists == "vol_present"

    with user_set(client):
        delete_code, _ = _delete(client, volume_resource)
        if volume_exists:
            post_code, _ = _post(client, volume_resource)
            assert post_code == 201
        else:
            assert _get(client, volume_resource)[0] == 404

    return (volume_resource, volume_exists, authorised)


@contextmanager
def maybe_authorised(client, authorised):
    if authorised:
        with user_set(client):
            yield
    else:
        yield


@params_namespaces
def test_list_no_volumes(client, namespace):
    code, response = _get(client, "/{}/volumes".format(namespace))
    assert code == 200
    assert response == []


@params_namespaces
def test_post_to_existing_volume_errors(client, namespace):
    volume_name = "samevolume"
    resource = '/{}/volumes/{}'.format(namespace, volume_name)
    with user_set(client):
        post_code, post_response = _post(client, resource, data={})
        assert post_code == 201
        assert post_response
        assert 'name' in post_response
        post_code, post_response = _post(client, resource, data={})
    assert post_code == 400

    get_code, stored_resource = _get(client, resource)
    assert get_code == 200
    assert 'errors' not in stored_resource
    assert stored_resource['name'] == volume_name

    assert len(_get(client, '/{}/volumes'.format(namespace))[1]) == 1


@params_vol_ns_auth
def test_post_new_volume(client, namespace, auth, vol_exists, volume_name):
    resource, volume_exists, authorised = init_vols_from_params(client,
                                                                namespace,
                                                                auth,
                                                                vol_exists,
                                                                volume_name)

    with maybe_authorised(client, authorised):
        post_code, post_response = _post(client, resource, data={})

    get_code, stored_resource = _get(client, resource)

    if not authorised:
        assert post_code == 403
        assert post_response
        if not volume_exists:
            assert get_code == 404
    elif not volume_exists:
        assert post_code == 201
        assert post_response
        assert 'name' in post_response
        assert get_code == 200
        assert 'errors' not in stored_resource
        assert stored_resource['name'] == volume_name
    else:
        assert post_code == 400


@params_vol_ns_auth
def test_get_volume(client, auth, vol_exists, volume_name, namespace):
    volume, volume_exists, _authorised = init_vols_from_params(client,
                                                               namespace,
                                                               auth,
                                                               vol_exists,
                                                               volume_name)

    get_code, get_response = _get(client, volume)

    if not volume_exists:
        assert get_code == 404
        assert 'message' in get_response
    else:
        assert get_code == 200


@params_vol_ns_auth
def test_delete_volume(client, auth, vol_exists, volume_name, namespace):
    resource, volume_exists, authorised = init_vols_from_params(client,
                                                                namespace,
                                                                auth,
                                                                vol_exists,
                                                                volume_name)
    with maybe_authorised(client, authorised):
        code, response = _delete(client, resource)

    get_code, _get_response = _get(client, resource)

    if not authorised:
        assert code == 403
        if volume_exists:
            assert get_code == 200
    elif not volume_exists:
        assert code == 404
    else:
        assert code == 204
        assert get_code == 404


@params_namespaces
def test_create_wrong_group(client, namespace):
    resource = '/{}/volumes/wrong_group'.format(namespace)

    with user_set(client, user={'group': ['completely-unauthorised-group']}):
        post_code, _post_result = _post(client, resource, data={})

    assert post_code == 403
    get_code, _get_response = _get(client, resource)
    assert get_code == 404


@params_namespaces
def test_create_snapshot_from_volume(client, namespace):
    volume = '/{}/volumes/{}'.format(namespace, uuid.uuid1())

    with user_set(client):
        _post_code, _post_result = _post(client, volume,
                                         data={'max_autosize': 42,
                                               'autosize_increment': 12})

    snapshot_name = "{}".format("shotsnap", namespace)
    snapshot = '{}/snapshots/{}'.format(volume, snapshot_name)

    with user_set(client):
        snapshot_post_code, _snapshot_post_result = _post(client, snapshot, data={})

    assert snapshot_post_code == 201

    get_code, get_result = _get(client, snapshot)
    assert get_code == 200
    assert get_result['name'] == snapshot_name

    snapshots_get_code, get_results = _get(client, '{}/snapshots'.format(volume))
    assert snapshots_get_code == 200

    assert any(map(lambda x: x['name'] == snapshot_name, get_results))
    assert len(get_results) == 1


@params_namespaces
def test_rollback_from_snapshot(client, namespace):
    volume = '/{}/volumes/{}'.format(namespace, uuid.uuid1())

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _post(client, volume, data={})
        _post(client, snapshot_resource, data={})
        post_code, post_result = _post(client, volume,
                                       data={'from_snapshot':
                                             snapshot_name})

    assert post_code == 201
    # No way of verifying that the volume was actually restored.


@params_namespaces
def test_clone_from_snapshot(client, namespace):
    master_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, master_name)
    clone_volume = '{}/volumes/{}'.format(namespace, "clone")

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _post(client, volume, data={})
        _post(client, snapshot_resource, data={})
        post_code, post_result = _post(client,
                                       clone_volume,
                                       data={'from_snapshot': snapshot_name,
                                             'from_volume': master_name})

    assert post_code == 201
    assert _get(client, clone_volume) == _get(client, volume)


@params_namespaces
def test_clone_from_snapshot_name_collission(client, namespace):
    volume_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    snapshot_name = "snapshot"
    snapshot_resource = "{}/snapshots/{}".format(volume, snapshot_name)

    with user_set(client):
        _post(client, volume, data={})
        _post(client, snapshot_resource, data={})
        post_code, post_result = _post(client,
                                       volume,
                                       data={'from_snapshot': snapshot_name,
                                             'from_volume': volume_name})
    assert post_code == 400
    assert 'message' in post_result
    assert 'in use' in post_result['message']


@params_namespaces
def test_clone_from_snapshot_source_does_not_exist(client, namespace):
    volume_name = str(uuid.uuid1())
    volume = '/{}/volumes/{}'.format(namespace, volume_name)

    with user_set(client):
        post_code, post_result = _post(client,
                                       volume,
                                       data={'from_snapshot': 'no-snapshot',
                                             'from_volume': volume_name})
    assert post_code == 404
    assert 'message' in post_result
    assert 'No such volume' in post_result['message']


@given(patch_args=patch_arguments())
@params_vol_ns_auth
def test_patch_volume(client, namespace, vol_exists, auth,
                      volume_name, patch_args):
    volume, volume_exists, authorised = init_vols_from_params(client,
                                                              namespace,
                                                              auth,
                                                              vol_exists,
                                                              volume_name)

    with maybe_authorised(client, authorised):
            patch_code, _patch_result = _patch(client, volume, data=patch_args)

    _get_code, get_result = _get(client, volume)

    if not authorised:
        assert patch_code == 403
    elif not volume_exists and patch_args:
        assert patch_code == 404
    else:
        if patch_args:
            assert patch_code == 200
            for key, value in patch_args.items():
                assert get_result[key] == value
        else:
            assert patch_code == 400


@params_volume_names
@params_namespaces
def test_delete_snapshot_nonexistent_snapshot_and_volume(client, namespace, volume_name):
    volume = '/{}/volumes/{}-{}'.format(namespace, volume_name, namespace)
    snapshot = '{}/snapshots/my-snapshot'.format(volume, volume_name)

    with user_set(client):
        delete_code, _delete_result = _delete(client, snapshot)

    assert delete_code == 404

    delete_code = None

    with user_set(client):
        _put(client, volume)
        delete_code, _delete_result = _delete(client, snapshot)

    assert delete_code == 404


@params_volume_names
@params_namespaces
@params_auth_status
def test_delete_snapshot(client, namespace, auth, volume_name):
    volume = '/{}/volumes/{}-{}'.format(namespace, volume_name, namespace)
    snapshot = '{}/snapshots/my-snapshot'.format(volume, volume_name)
    authorised = auth == "authorised"

    with user_set(client):
        _post(client, volume)
        post_code, _ = _post(client, snapshot, data={})
        assert post_code == 201
        get_before, _ = _get(client, snapshot)
        assert get_before == 200

    with maybe_authorised(client, authorised):
        delete_code, _delete_result = _delete(client, snapshot)

    if authorised:
        assert delete_code == 204
    else:
        assert delete_code == 403

    get_after, _ = _get(client, snapshot)

    if authorised:
        assert get_after == 404
    else:
        assert get_after == 200


@params_volume_names
@params_namespaces
def test_get_empty_locks(client, namespace, volume_name):
    volume = '/{}/volumes/{}'.format(namespace, volume_name, namespace)
    with user_set(client):
        _post(client, volume)
    get_code, get_result = _get(client, volume + '/locks')

    assert get_code == 200
    assert get_result == []


@params_vol_ns_auth
def test_lock_volume(client, namespace, auth, vol_exists, volume_name):
    volume, volume_exists, authorised = init_vols_from_params(client,
                                                              namespace,
                                                              auth,
                                                              vol_exists,
                                                              volume_name)
    host = "dbhost.cern.ch"
    lock = '{}/locks/{}'.format(volume, host)

    with maybe_authorised(client, authorised):
        put_code, _ = _put(client, lock)

    get_code, get_result = _get(client, volume + '/locks')

    if not authorised:
        assert put_code == 403
        if volume_exists:
            assert get_code == 200
            assert len(get_result) == 0
    elif volume_exists:
        assert len(get_result) == 1
        assert get_result[0]['host'] == host
    else:
        assert put_code == 404


@params_vol_ns_auth
def test_force_lock_on_volume(client, namespace, auth, vol_exists, volume_name):
    volume, volume_exists, authorised = init_vols_from_params(client,
                                                              namespace,
                                                              auth,
                                                              vol_exists,
                                                              volume_name)
    host = "dbhost.cern.ch"
    lock = '{}/locks/{}'.format(volume, host)

    if volume_exists:
        with user_set(client):
            _put(client, lock)

    with maybe_authorised(client, authorised):
        delete_code, _ = _delete(client, lock)

    get_code, get_result = _get(client, volume + '/locks')

    if not authorised:
        assert delete_code == 403
        if volume_exists:
            assert len(get_result) == 1
            assert get_result[0]['host'] == host
    elif not volume_exists:
        assert get_code == 404
        assert delete_code == 404
    else:
        assert get_code == 200
        assert delete_code == 204
        assert len(get_result) == 0


@params_volume_names
@params_namespaces
def test_lock_locked_volume(client, namespace, volume_name):
    host1 = "dbhost1.cern.ch"
    host2 = "dbhost2.cern.ch"
    volume = '/{}/volumes/{}'.format(namespace, volume_name)
    lock1 = '{}/locks/{}'.format(volume, host1)
    lock2 = '{}/locks/{}'.format(volume, host2)

    with user_set(client):
        _post(client, volume)
        put_code, _ = _put(client, lock1)
        assert put_code == 201

        put2_code, _ = _put(client, lock2)
        assert put2_code == 400

        del_code, _ = _delete(client, lock2)
        assert del_code == 204

        put2_code_again, _ = _put(client, lock2)
        assert put_code == 201


@params_volume_names
@params_namespaces
def test_lock_volume_idempotent(client, namespace, volume_name):
    host = "dbhost1.cern.ch"
    volume = '/{}/volumes/{}'.format(namespace, volume_name)
    lock = '{}/locks/{}'.format(volume, host)

    with user_set(client):
        _post(client, volume)
        put_code, _ = _put(client, lock)
        assert put_code == 201

        put2_code, _ = _put(client, lock)
        assert put2_code == 201

    get_code, get_result = _get(client, volume + '/locks')
    assert get_code == 200
    assert get_result == [{'host': host}]


@params_ns_auth
def test_get_acl(client, namespace, auth):
    authorised = auth == "authorised"

    if authorised:
        with user_set(client):
            get_code, get_result = _get(client, "{}/export".format(namespace))
    else:
        get_code, get_result = _get(client, "{}/export".format(namespace))

    # Assertions:
    if not authorised:
        assert get_code == 403
    else:
        # Exists and authorised => 200 OK + data
        assert get_code == 200

        # We have no access rules defined at this time
        assert get_result == []


@given(policy_name=policy_name_strings())
@params_ns_auth
def test_put_acl(client, namespace, auth, policy_name):
    authorised = auth == "authorised"

    policy = '{}/export/{}'.format(namespace, policy_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch", "*foo.cern.ch"]

    with maybe_authorised(client, authorised):
        post_code, _post_result = _post(client, policy, data={'rules': rules})

    with user_set(client):
        get_code, get_result = _get(client, policy)
        _, get_all = _get(client, namespace + "/export")

    # Assertions:
    if not authorised:
        assert post_code == 403
    else:
        assert post_code == 201
        assert get_code == 200

        assert get_result
        assert get_result['name'] == policy_name
        assert get_result['rules'] == rules
        assert get_result in get_all


@given(policy_name=policy_name_strings())
@params_policy_presence
@params_ns_auth
def test_delete_acl(client, namespace, auth, policy_status, policy_name):
    authorised = auth == "authorised"
    policy_exists = policy_status == "policy_present"

    policy = '{}/export/{}'.format(namespace, policy_name)

    rules = []  # type: List[str]

    with user_set(client):
        if policy_exists:
            _post(client, policy, data={'rules': rules})
        else:
            del_code, _ = _delete(client, policy)
            assert del_code == 404 or del_code == 204

    with maybe_authorised(client, authorised):
        del_code, _del_result = _delete(client, policy)
    with user_set(client):
        get_code, _get_result = _get(client, policy)
        _, get_all = _get(client, namespace + "/export")

    if not authorised:
        assert del_code == 403
        if policy_exists:
            assert get_code == 200
    elif not policy_exists:
        assert del_code == 404
    else:
        assert del_code == 204
        assert get_code == 404
        assert get_all == []


@given(policy_name=policy_name_strings())
@params_policy_presence
@params_ns_auth
def test_put_export_rule(client, namespace, auth, policy_status, policy_name):
    authorised = auth == "authorised"
    policy_exists = policy_status == "policy_present"
    policy = '{}/export/{}'.format(namespace, policy_name)

    rules = ["127.0.0.1", "10.10.10.1/24"]
    put_codes = []

    with user_set(client):
        if policy_exists:
            _post(client, policy, data={'rules': []})
        else:
            del_code, _ = _delete(client, policy)
            assert del_code == 404 or del_code == 204

    with maybe_authorised(client, authorised):
        for rule in rules:
            put_code, _ = _put(client, ("{}/{}".format(policy, rule)))
            put_codes.append(put_code)

    with user_set(client):
        get_code, get_result = _get(client, policy)

    if not authorised:
        assert all(filter(lambda c: c == 403, put_codes))
        if policy_exists:
            # No changes recorded
            assert get_result['rules'] == []
    elif not policy_exists:
        assert all(filter(lambda c: c == 404, put_codes))
    else:
        assert all(filter(lambda c: c == 204, put_codes))
        assert get_code == 200
        assert get_result['rules'] == rules


@given(policy_name=policy_name_strings())
@params_policy_presence
@params_ns_auth
def test_delete_export_rule(client, namespace, auth,  policy_status, policy_name):
    authorised = auth == "authorised"
    policy_exists = policy_status == "policy_present"
    policy = '{}/export/{}'.format(namespace, policy_name)

    rules = ["127.0.0.1", "10.10.10.1/24"]
    delete_codes = []

    with user_set(client):
        if policy_exists:
            _delete(client, policy)
            _post(client, policy, data={'rules': rules})
        else:
            del_code, _ = _delete(client, policy)
            assert del_code == 404 or del_code == 204

    with maybe_authorised(client, authorised):
        for rule in rules:
            delete_code, _ = _delete(client, ("{}/{}".format(policy, rule)))
            delete_codes.append(delete_code)

    with user_set(client):
        get_code, get_result = _get(client, policy)

    if not authorised:
        assert all(filter(lambda c: c == 403, delete_codes))
        if policy_exists:
            # No changes recorded
            assert get_result['rules'] == rules
    elif not policy_exists:
        assert all(filter(lambda c: c == 404, delete_codes))
    else:
        assert all(filter(lambda c: c == 201, delete_codes))
        assert get_code == 200
        assert get_result['rules'] == []
