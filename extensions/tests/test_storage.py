from extensions.storage import DummyStorage

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
