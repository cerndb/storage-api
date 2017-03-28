from extensions.storage import DummyStorage, NetappStorage, StorageBackend # noqa

import uuid
import functools
import os
from unittest import mock
from contextlib import contextmanager

import pytest
import netapp.api
import betamax


DEFAULT_VOLUME_SIZE = 30000000


def id_from_vol(v, backend):
    if isinstance(backend, NetappStorage):
        return "{}:{}".format(v['filer_address'], v['junction_path'])
    else:
        return v['name']


def new_volume(backend):
    run_id = 42
    name = 'nothing:/volumename_{}'.format(run_id)
    try:
        new_vol = backend.create_volume(name,
                                        name="volume_name_{}".format(run_id),
                                        size_total=DEFAULT_VOLUME_SIZE)
    except KeyError:
        new_vol = backend.get_volume(name)

    return new_vol


def delete_volume(backend, volume_name):
    if not isinstance(backend, NetappStorage):
        return

    server = backend.server
    try:
        server.unmount_volume(volume_name)
        server.take_volume_offline(volume_name)
        server.destroy_volume(volume_name)
    except netapp.api.APIError:
        pass


@contextmanager
def ephermeral_volume(backend):
    vol = new_volume(backend)
    try:
        yield vol
    finally:
        delete_volume(backend, vol['name'])


def on_all_backends(func):
    """
    This has to be a separate decorator because the storage
    parameter must be initialised on every run with a fresh object.

    Will parametrise the decorated test to run once for every type of
    storage provided here.
    """

    vserver = os.environ.get('ONTAP_VSERVER', 'vs1rac11')
    ontap_host = os.environ.get('ONTAP_HOST', 'dbnasa-cluster-mgmt')
    ontap_username = os.environ.get('ONTAP_USERNAME', "user-placeholder")
    ontap_password = os.environ.get('ONTAP_PASSWORD', "password-placeholder")

    netapp_server = netapp.api.Server(hostname=ontap_host,
                                      username=ontap_username,
                                      password=ontap_password,
                                      vserver=vserver)
    backend = NetappStorage(netapp_server=netapp_server)
    recorder = betamax.Betamax(backend.server.session)

    @functools.wraps(func)
    @pytest.mark.parametrize("storage,recorder", [(DummyStorage(), mock.MagicMock()),
                                                  (backend, recorder)])
    def backend_wrapper(*args, **kwargs):
        func(*args, **kwargs)
    return backend_wrapper


@on_all_backends
def test_get_no_volumes(storage, recorder):
    if not isinstance(storage, NetappStorage):
        assert storage.volumes == []


@on_all_backends
def test_get_nonexistent_volume(storage, recorder):
    with recorder.use_cassette('nonexistent_value'):
        with pytest.raises(KeyError):
            storage.get_volume('does-not-exist')


@on_all_backends
def test_create_get_volume(storage, recorder):
    with recorder.use_cassette('create_get_volume'):
        new_vol = storage.create_volume('nothing:/volumename',
                                        name="volume_name",
                                        size_total=DEFAULT_VOLUME_SIZE)
        volume = storage.get_volume('nothing:/volumename')
        assert new_vol == volume
        assert volume
        assert volume['size_total'] >= DEFAULT_VOLUME_SIZE
        assert volume['size_total'] <= DEFAULT_VOLUME_SIZE * 10
        assert volume in storage.volumes


@on_all_backends
def test_create_already_existing_volume(storage, recorder):
    with recorder.use_cassette('create_existing_volume'):
        with ephermeral_volume(storage) as v:
            id = id_from_vol(v, storage)
            with pytest.raises(KeyError):
                storage.create_volume(id,
                                      name=v['name'],
                                      size_total=DEFAULT_VOLUME_SIZE)


@on_all_backends
def test_restrict_volume(storage, recorder):
    with recorder.use_cassette('restrict_volume'):
        with ephermeral_volume(storage) as vol:
            storage.restrict_volume(id_from_vol(vol, storage))
            vol not in storage.volumes


@on_all_backends
def test_patch_volume(storage, recorder):
    with recorder.use_cassette('patch_volume'):
        with ephermeral_volume(storage) as vol:
            storage.patch_volume(id_from_vol(vol, storage),
                                 autosize_enabled=True,
                                 max_autosize=2*DEFAULT_VOLUME_SIZE)

            v = storage.get_volume(id_from_vol(vol, storage))
            assert v['autosize_enabled'] is True
            assert v['max_autosize'] >= 2*DEFAULT_VOLUME_SIZE
            assert v['max_autosize'] <= 3*DEFAULT_VOLUME_SIZE


@on_all_backends
def test_get_no_locks(storage, recorder):
    with recorder.use_cassette('get_no_locks'):
        with ephermeral_volume(storage) as vol:
            assert storage.locks(id_from_vol(vol, storage)) is None


@on_all_backends
def test_add_lock(storage, recorder):
    if isinstance(storage, NetappStorage):
        # NetApp back-end cannot add locks
        return

    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' == storage.locks('volumename')


@on_all_backends
def test_remove_lock(storage, recorder):
    if isinstance(storage, NetappStorage):
        # NetApp cannot add locks
        return

    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' != storage.locks('volumename')
    assert storage.locks('volumename') is None
    storage.create_lock('volumename', 'db2.cern.ch')
    assert 'db2.cern.ch' == storage.locks('volumename')


@on_all_backends
def test_remove_lock_wrong_host(storage, recorder):
    if isinstance(storage, NetappStorage):
        # NetApp cannot add locks
        return

    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'othermachine.cern.ch')

    assert storage.locks('volumename') == 'db.cern.ch'


@on_all_backends
def test_lock_locked(storage, recorder):
    if isinstance(storage, NetappStorage):
        # NetApp cannot add locks
        return

    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')

    with pytest.raises(ValueError):
        storage.create_lock('volumename', 'db2.cern.ch')


@on_all_backends
def test_get_snapshots(storage, recorder):
    with recorder.use_cassette('get_snapshots'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            storage.create_snapshot(volume_id, snapshot_name="snapshot-new")
            snapshots = storage.get_snapshots(volume_id)
            assert len(snapshots) == 1
            assert storage.get_snapshot(volume_id, "snapshot-new")['name'] == "snapshot-new"
            assert snapshots[0]['name'] == "snapshot-new"


@on_all_backends
def test_set_policy(storage, recorder):
    rules = ["host1.db.cern.ch", "db.cern.ch", "foo.cern.ch"]

    with recorder.use_cassette('set_policy'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            storage.create_policy("a_policy_400", rules)
            storage.set_policy(volume_name=volume_id,
                               policy_name="a_policy_400")

            vol_after = storage.get_volume(volume_id)
            assert vol_after['active_policy_name'] == "a_policy_400"

        storage.remove_policy("a_policy_400")


@on_all_backends
def test_delete_policy(storage, recorder):
    rules = ["host1.db.cern.ch", "db.cern.ch"]
    policy_name = "a_policy_924"

    with recorder.use_cassette('delete_policy'):
        storage.create_policy(policy_name, rules)
        assert policy_name in [p['name'] for p in storage.policies]
        storage.remove_policy(policy_name)
        assert policy_name not in [p['name'] for p in storage.policies]

        storage.create_policy(policy_name, rules)
        assert policy_name in [p['name'] for p in storage.policies]
        storage.remove_policy(policy_name)
        assert policy_name not in [p['name'] for p in storage.policies]


@on_all_backends
def test_remove_policy_no_policy_raises_key_error(storage, recorder):
    with recorder.use_cassette('remove_nonexistent_policy'):
        with pytest.raises(KeyError):
            storage.remove_policy("a_policy_that_doesnt_exist")


@on_all_backends
def test_clone_volume(storage, recorder):
    if isinstance(storage, NetappStorage):
        # Not currently supported :(
        return

    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)

    with pytest.raises(KeyError):
        storage.clone_volume("vol2-clone",
                             from_volume_name=volume_name,
                             from_snapshot_name="mysnap")

    storage.create_snapshot(volume_name=volume_name, snapshot_name="mysnap")
    storage.clone_volume("vol2-clone",
                         from_volume_name=volume_name,
                         from_snapshot_name="mysnap")

    vol = storage.get_volume(volume_name)
    clone = storage.get_volume("vol2-clone")

    with pytest.raises(ValueError):
        storage.clone_volume(volume_name,
                             from_volume_name=volume_name,
                             from_snapshot_name="mysnap")

    assert vol == clone


@on_all_backends
def test_delete_snapshot(storage, recorder):
    snapshot_name = "snapshot123"

    with recorder.use_cassette('remove_snapshot'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)

            with pytest.raises(KeyError):
                storage.delete_snapshot(volume_id, snapshot_name)

            storage.create_snapshot(volume_id, snapshot_name)
            storage.delete_snapshot(volume_id, snapshot_name)
            assert storage.get_snapshots(volume_id) == []


@on_all_backends
def test_rollback_volume(storage, recorder):
    if isinstance(storage, NetappStorage):
        # Not currently supported :(
        return

    volume_name = str(uuid.uuid1())
    storage.create_volume(volume_name=volume_name)

    with pytest.raises(KeyError):
        storage.rollback_volume(volume_name, restore_snapshot_name=volume_name)

    storage.create_snapshot(volume_name, volume_name)
    storage.rollback_volume(volume_name, restore_snapshot_name=volume_name)
    # FIXME: no way of verifying that something was actually done


@on_all_backends
def test_ensure_policy_rule_present(storage, recorder):
    rule = "127.0.0.1"
    policy_name = "policy126"

    with recorder.use_cassette('ensure_policy_rule_present',
                               match_requests_on=['method', 'uri']):
        storage.create_policy(policy_name=policy_name,
                              rules=[])

        storage.ensure_policy_rule_absent(policy_name=policy_name,
                                          rule=rule)

        storage.ensure_policy_rule_present(policy_name=policy_name,
                                           rule=rule)

        all_policies = storage.get_policy(policy_name=policy_name)

        assert all_policies == [rule]

        for r in 4 * [rule]:
            storage.ensure_policy_rule_present(policy_name=policy_name,
                                               rule=r)

        assert storage.get_policy(policy_name=policy_name) == [rule]

        storage.remove_policy(policy_name)


@on_all_backends
def test_ensure_policy_rule_absent(storage, recorder):
    rule = "127.0.0.1"
    policy_name = "a_policy_53"
    try:
        with recorder.use_cassette('ensure_policy_rule_absent'):
            storage.create_policy(policy_name=policy_name,
                                  rules=[rule])

            assert rule in storage.get_policy(policy_name=policy_name)

            for _ in range(1, 3):
                storage.ensure_policy_rule_absent(policy_name=policy_name,
                                                  rule=rule)

            assert storage.get_policy(policy_name=policy_name) == []
    finally:
        try:
            storage.remove_policy(policy_name=policy_name)
        except KeyError:
            pass


@on_all_backends
def test_repr_doesnt_crash(storage, recorder):
    assert repr(storage)


@on_all_backends
def test_netapp_name_jp_both_work(storage, recorder):
    if not isinstance(storage, NetappStorage):
        # Only applies to netapp
        return

    with recorder.use_cassette('jp_equals_name_node'):
        with ephermeral_volume(storage) as vol:
            node_colon_jp = id_from_vol(vol, storage)
            from_jp_name = storage.get_volume(node_colon_jp)
            from_name_only = storage.get_volume(vol['name'])
            assert from_jp_name == from_name_only


@on_all_backends
def test_netapp_create_volume_no_node(storage, recorder):
    if not isinstance(storage, NetappStorage):
        # Only applies to netapp
        return

    with recorder.use_cassette('tricky_netapp_create_no_node'):
        try:
            new_vol = storage.create_volume(':/volumename',
                                            name="volume_name",
                                            size_total=DEFAULT_VOLUME_SIZE)
            volume = storage.get_volume(new_vol['name'])
            assert new_vol == volume
            assert volume in storage.volumes
            assert 'filer_address' in new_vol
        finally:
            delete_volume(storage, new_vol['name'])


@on_all_backends
def test_netapp_create_volume_as_name(storage, recorder):
    if not isinstance(storage, NetappStorage):
        # Only applies to netapp
        return

    with recorder.use_cassette('tricky_netapp_create_as_name'):
        try:
            new_vol = storage.create_volume("volume_name_test_32",
                                            junction_path="/volume_name_test",
                                            size_total=DEFAULT_VOLUME_SIZE)
            assert new_vol['junction_path'] == "/volume_name_test"
            assert new_vol['name'] == "volume_name_test_32"
        finally:
            delete_volume(storage, new_vol['name'])


@on_all_backends
def test_netapp_create_volume_name_missing(storage, recorder):
    if not isinstance(storage, NetappStorage):
        # Only applies to netapp
        return

    with pytest.raises(ValueError):
        storage.create_volume(':/volumename',
                              size_total=DEFAULT_VOLUME_SIZE)


@on_all_backends
def test_netapp_create_volume_jp_missing(storage, recorder):
    if not isinstance(storage, NetappStorage):
        # Only applies to netapp
        return

    with pytest.raises(ValueError):
        storage.create_volume("volume_name_test_32",
                              size_total=DEFAULT_VOLUME_SIZE)
