from extensions.storage import DummyStorage, NetappStorage, StorageBackend # noqa

import uuid
import functools
import os

import pytest
import netapp.api


def is_ontap_env_setup():
    return ('ONTAP_HOST' in os.environ
            and 'ONTAP_USERNAME' in os.environ
            and 'ONTAP_PASSWORD' in os.environ
            and 'ONTAP_VSERVER' in os.environ)


def on_all_backends(func):
    """
    This has to be a separate decorator because the storage
    parameter must be initialised on every run with a fresh object.

    Will parametrise the decorated test to run once for every type of
    storage provided here.
    """
    backends = [DummyStorage()]  # type: List[StorageBackend]

    if is_ontap_env_setup():
        server_host = os.environ['ONTAP_HOST']
        server_username = os.environ['ONTAP_USERNAME']
        server_password = os.environ['ONTAP_PASSWORD']
        vserver = os.environ['ONTAP_VSERVER']
        server = netapp.api.Server(hostname=server_host,
                                   username=server_username,
                                   password=server_password,
                                   vserver=vserver)
        backends.append(NetappStorage(netapp_server=server))

    @functools.wraps(func)
    @pytest.mark.parametrize("storage", backends)
    def backend_wrapper(*args, **kwargs):
        func(*args, **kwargs)
    return backend_wrapper


@on_all_backends
def test_get_no_volumes(storage):
    if not isinstance(storage, NetappStorage):
        assert storage.volumes == []


@on_all_backends
def test_get_nonexistent_volume(storage):
    with pytest.raises(KeyError):
        storage.get_volume('does-not-exist')


@on_all_backends
def test_create_get_volume(storage):
    storage.create_volume('volumename',
                          size_total=1024)
    volume = storage.get_volume('volumename')
    assert volume
    assert volume['size_total'] == 1024
    assert storage.volumes == [volume]


@on_all_backends
def test_create_already_existing_volume(storage):
    storage.create_volume('volumename',
                          size_total=1024)
    with pytest.raises(KeyError):
        storage.create_volume('volumename',
                              size_total=1024)


@on_all_backends
def test_restrict_volume(storage):
    storage.create_volume('volumename',
                          size_total=1024)
    storage.restrict_volume('volumename')
    storage.volumes == []
    with pytest.raises(KeyError):
        storage.get_volume('volumename')


@on_all_backends
def test_patch_volume(storage):
    storage.create_volume('volumename',
                          size_total=1024)
    storage.patch_volume('volumename', size_total=2056)

    v = storage.get_volume('volumename')

    assert v['size_total'] == 2056


@on_all_backends
def test_get_no_locks(storage):
    storage.create_volume('bork')
    assert storage.locks('bork') is None


@on_all_backends
def test_add_lock(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' == storage.locks('volumename')


@on_all_backends
def test_remove_lock(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' != storage.locks('volumename')
    assert storage.locks('volumename') is None
    storage.create_lock('volumename', 'db2.cern.ch')
    assert 'db2.cern.ch' == storage.locks('volumename')


@on_all_backends
def test_remove_lock_wrong_host(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'othermachine.cern.ch')

    assert storage.locks('volumename') == 'db.cern.ch'


@on_all_backends
def test_lock_locked(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')

    with pytest.raises(ValueError):
        storage.create_lock('volumename', 'db2.cern.ch')


@on_all_backends
def test_get_snapshots(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)

    storage.create_snapshot(volume_name, snapshot_name="snapshot-new")

    snapshots = storage.get_snapshots(volume_name)
    assert len(snapshots) == 1
    assert storage.get_snapshot(volume_name, "snapshot-new")['name'] == "snapshot-new"
    assert snapshots[0]['name'] == "snapshot-new"


@on_all_backends
def test_add_policy(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch", "*foo.cern.ch"]

    storage.create_policy(volume_name, "a policy", rules)

    policies = storage.policies(volume_name)

    assert len(policies) == 1
    assert policies[0][1] == rules
    assert storage.get_policy(volume_name, "a policy") == (policies[0][1])


@on_all_backends
def test_delete_policy(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch"]

    storage.create_policy(volume_name, "a policy", rules)
    storage.remove_policy(volume_name, "a policy")
    assert len(storage.policies(volume_name)) == 0

    storage.create_policy(volume_name, "a policy", rules)
    assert len(storage.policies(volume_name)) == 1


@on_all_backends
def test_delete_volume_policies_deleted_also(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch"]
    policy_name = "a policy"

    storage.create_policy(volume_name, policy_name, rules)
    storage.restrict_volume(volume_name)

    storage.create_volume(volume_name=volume_name)
    assert len(storage.policies(volume_name)) == 0


@on_all_backends
def test_add_policy_no_volume_raises_key_error(storage):
    volume_name = uuid.uuid1()
    with pytest.raises(KeyError):
        storage.create_policy(volume_name, "a policy", rules=[])


@on_all_backends
def test_remove_policy_no_policy_raises_key_error(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name)
    with pytest.raises(KeyError):
        storage.remove_policy(volume_name, "a policy")


@on_all_backends
def test_clone_volume(storage):
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
def test_delete_snapshot(storage):
    volume_name = str(uuid.uuid1())
    storage.create_volume(volume_name=volume_name)

    with pytest.raises(KeyError):
        storage.delete_snapshot(volume_name, volume_name)

    storage.create_snapshot(volume_name, volume_name)
    storage.delete_snapshot(volume_name, volume_name)
    assert storage.get_snapshots(volume_name) == []


@on_all_backends
def test_rollback_volume(storage):
    volume_name = str(uuid.uuid1())
    storage.create_volume(volume_name=volume_name)

    with pytest.raises(KeyError):
        storage.rollback_volume(volume_name, restore_snapshot_name=volume_name)

    storage.create_snapshot(volume_name, volume_name)
    storage.rollback_volume(volume_name, restore_snapshot_name=volume_name)
    # FIXME: no way of verifying that something was actually done


@on_all_backends
def test_ensure_policy_rule_present(storage):
    volume_name = uuid.uuid1()
    rule = "127.0.0.1/24"
    storage.create_volume(volume_name=volume_name)
    storage.create_policy(volume_name=volume_name, policy_name="policy",
                          rules=[])

    storage.ensure_policy_rule_absent(volume_name,
                                      policy_name="policy",
                                      rule=rule)

    storage.ensure_policy_rule_present(volume_name,
                                       policy_name="policy",
                                       rule=rule)

    all_policies = storage.get_policy(volume_name, policy_name="policy")

    assert all_policies == [rule]

    for r in 4 * [rule]:
        storage.ensure_policy_rule_present(volume_name,
                                           policy_name="policy",
                                           rule=r)

    assert storage.get_policy(volume_name, policy_name="policy") == [rule]


@on_all_backends
def test_ensure_policy_rule_absent(storage):
    volume_name = str(uuid.uuid1())
    rule = "127.0.0.1/24"
    storage.create_volume(volume_name=volume_name)
    storage.create_policy(volume_name=volume_name, policy_name="policy",
                          rules=[rule])

    assert rule in storage.get_policy(volume_name, policy_name="policy")

    for _ in range(1, 3):
        storage.ensure_policy_rule_absent(volume_name, policy_name="policy",
                                          rule=rule)

    assert storage.get_policy(volume_name, policy_name="policy") == []


@on_all_backends
def test_repr_doesnt_crash(storage):
    assert repr(storage)
