from extensions.storage import DummyStorage

import uuid

import pytest


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_get_no_volumes(storage):
    assert storage.volumes == []


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_get_nonexistent_volume(storage):
    with pytest.raises(KeyError):
        storage.get_volume('does-not-exist')


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_get_no_locks(storage):
    storage.create_volume('bork')
    assert storage.locks('bork') is None


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_add_lock(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' == storage.locks('volumename')


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_remove_lock(storage):
    storage.create_volume('volumename')
    storage.create_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'db.cern.ch')

    assert 'db.cern.ch' != storage.locks('volumename')
    assert storage.locks('volumename') is None


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_get_snapshots(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(name=volume_name)

    storage.create_snapshot(volume_name, snapshot_name="snapshot-new")

    assert len(storage.get_snapshots(volume_name)) == 1
    assert storage.get_snapshot(volume_name, "snapshot-new")['name'] == "snapshot-new"


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_add_policy(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch", "*foo.cern.ch"]

    storage.create_policy(volume_name, "a policy", rules)

    policies = storage.policies(volume_name)

    assert len(policies) == 1
    assert policies[0]['policy_name'] == "a policy"
    assert policies[0]['rules'] == rules


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_delete_policy(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch"]

    storage.create_policy(volume_name, "a policy", rules)
    storage.remove_policy(volume_name, "a policy")
    assert len(storage.policies(volume_name)) == 0


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_delete_volume_policies_deleted_also(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(name=volume_name)
    rules = ["host1.db.cern.ch", "*db.cern.ch"]
    policy_name = "a policy"

    storage.create_policy(volume_name, policy_name, rules)
    storage.restrict_volume(volume_name)

    storage.create_volume(name=volume_name)
    assert len(storage.policies(volume_name)) == 0


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_add_policy_no_volume_raises_key_error(storage):
    volume_name = uuid.uuid1()
    with pytest.raises(KeyError):
        storage.create_policy(volume_name, "a policy", rules=[])


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_remove_policy_no_policy_raises_key_error(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(volume_name)
    with pytest.raises(KeyError):
        storage.remove_policy(volume_name, "a policy")
