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
    assert storage.locks == []


@pytest.mark.parametrize("storage", [DummyStorage()])
def test_get_snapshots(storage):
    volume_name = uuid.uuid1()
    storage.create_volume(name=volume_name)

    storage.create_snapshot(volume_name, snapshot_name="snapshot-new")

    assert len(storage.get_snapshots(volume_name)) == 1
    assert storage.get_snapshot(volume_name, "snapshot-new")['name'] == "snapshot-new"
