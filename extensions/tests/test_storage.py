from extensions.storage import DummyStorage

import pytest


@pytest.mark.parametrize("storage_type", [DummyStorage])
def test_get_no_volumes(storage_type):
    storage = storage_type()
    assert storage.volumes == []


@pytest.mark.parametrize("storage_type", [DummyStorage])
def test_dummy_storage_get_nonexistent_volume(storage_type):
    storage = storage_type()

    with pytest.raises(KeyError):
        storage.get_volume('does-not-exist')
