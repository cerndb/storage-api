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
    assert storage.locks('bork') == []


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_add_lock(storage):
    storage.create_volume('volumename')
    storage.add_lock('volumename', 'db.cern.ch')

    assert {'host': 'db.cern.ch'} in storage.locks('volumename')


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_remove_lock(storage):
    storage.create_volume('volumename')
    storage.add_lock('volumename', 'db.cern.ch')
    storage.remove_lock('volumename', 'db.cern.ch')

    assert {'host': 'db.cern.ch'} not in storage.locks('volumename')
    assert storage.locks('volumename') == []


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

    storage.add_policy()
