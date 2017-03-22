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
    new_vol = backend.create_volume(name,
                                    name="volume_name_{}".format(run_id),
                                    size_total=DEFAULT_VOLUME_SIZE)
    return new_vol


def delete_volume(backend, volume_name):
    if not isinstance(backend, NetappStorage):
        return

    server = backend.server
    with server.with_vserver(backend.vserver):
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
                                      password=ontap_password)
    backend = NetappStorage(netapp_server=netapp_server,
                            vserver=vserver)
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
    with recorder.use_cassette('patch_volume',
                               match_requests_on=['method', 'uri']):
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
def test_add_policy(storage, recorder):
    rules = ["host1.db.cern.ch", "*db.cern.ch", "*foo.cern.ch"]

    with recorder.use_cassette('add_policy'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            storage.create_policy(volume_id, "a policy", rules)
            policies = storage.policies(volume_id)

            assert len(policies) == 1
            assert policies[0][1] == rules
            assert storage.get_policy(volume_id, "a policy") == (policies[0][1])


@on_all_backends
def test_delete_policy(storage, recorder):
    rules = ["host1.db.cern.ch", "*db.cern.ch"]

    with recorder.use_cassette('delete_policy',
                               match_requests_on=['body',
                                                  'method',
                                                  'uri']):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            storage.create_policy(volume_id, "a policy", rules)
            storage.remove_policy(volume_id, "a policy")

            assert len(storage.policies(volume_id)) == 0

            storage.create_policy(volume_id, "a policy", rules)
            assert len(storage.policies(volume_id)) == 1


@on_all_backends
def test_delete_volume_policies_deleted_also(storage, recorder):
    if isinstance(storage, NetappStorage):
        # Restriction doesn't quite work this way on NetApp
        return

    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch"]
    policy_name = "a policy"

    storage.create_policy(volume_name, policy_name, rules)
    storage.restrict_volume(volume_name)

    storage.create_volume(volume_name=volume_name)
    assert len(storage.policies(volume_name)) == 0


@on_all_backends
def test_add_policy_no_volume_raises_key_error(storage, recorder):
    volume_name = "novolumeexists"
    with recorder.use_cassette('add_policy_nonexistent'):
        with pytest.raises(KeyError):
            storage.create_policy(volume_name, "a policy", rules=[])


@on_all_backends
def test_remove_policy_no_policy_raises_key_error(storage, recorder):
    with recorder.use_cassette('remove_nonexistent_policy'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            with pytest.raises(KeyError):
                storage.remove_policy(volume_id, "a policy")


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

    with recorder.use_cassette('remove_nonexistent_policy'):
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

    with recorder.use_cassette('ensure_policy_rule_present'):
        with ephermeral_volume(storage) as vol:
            volume_id = id_from_vol(vol, storage)
            storage.create_volume(volume_name=volume_id)
            storage.create_policy(volume_name=volume_id, policy_name="policy",
                                  rules=[])

            storage.ensure_policy_rule_absent(volume_id,
                                              policy_name="policy",
                                              rule=rule)

            storage.ensure_policy_rule_present(volume_id,
                                               policy_name="policy",
                                               rule=rule)

            all_policies = storage.get_policy(volume_id, policy_name="policy")

            assert all_policies == [rule]

            for r in 4 * [rule]:
                storage.ensure_policy_rule_present(volume_id,
                                                   policy_name="policy",
                                                   rule=r)

            assert storage.get_policy(volume_id, policy_name="policy") == [rule]


@on_all_backends
def test_ensure_policy_rule_absent(storage, recorder):
    rule = "127.0.0.1/24"
    with recorder.use_cassette('ensure_policy_rule_absent'):
        with ephermeral_volume(storage) as vol:
            volume_name = id_from_vol(vol, storage)
            storage.create_policy(volume_name=volume_name, policy_name="policy",
                                  rules=[rule])

            assert rule in storage.get_policy(volume_name, policy_name="policy")

            for _ in range(1, 3):
                storage.ensure_policy_rule_absent(volume_name, policy_name="policy",
                                                  rule=rule)

            assert storage.get_policy(volume_name, policy_name="policy") == []


@on_all_backends
def test_repr_doesnt_crash(storage, recorder):
    assert repr(storage)
