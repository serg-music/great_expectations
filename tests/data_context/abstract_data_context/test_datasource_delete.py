import pytest

from great_expectations import DataContext
from great_expectations.data_context import CloudDataContext
from great_expectations.data_context.types.base import DatasourceConfig


def test_datasource_delete_removes_from_cache_and_config_data_context(
    empty_data_context: DataContext, datasource_config: DatasourceConfig
):
    """context.datasource_delete should remove from the datasource cache and also config independent of the save_changes setting."""

    context: DataContext = empty_data_context
    datasource_name: str = "my_datasource"

    assert len(context.datasources) == 0
    datasource_config["name"] = datasource_name
    context.add_datasource(**datasource_config.to_dict())

    # ensure datasource is accessible
    assert len(context.datasources) == 1
    assert datasource_name in context.datasources
    assert datasource_name in context.config.datasources
    assert context._datasource_store.retrieve_by_name(datasource_name=datasource_name)

    context.delete_datasource(datasource_name)

    # ensure deleted
    assert len(context.datasources) == 0
    assert datasource_name not in context.datasources
    assert datasource_name not in context.config.datasources
    with pytest.raises(ValueError):
        assert not context._datasource_store.retrieve_by_name(
            datasource_name=datasource_name
        )


def test_datasource_delete_removes_from_cache_and_config_cloud_data_context(
    empty_cloud_data_context: CloudDataContext, datasource_config: DatasourceConfig
):
    """context.datasource_delete should remove from the datasource cache and also config independent of the save_changes setting."""

    context: DataContext = empty_cloud_data_context
    datasource_name: str = "my_datasource"

    assert len(context.datasources) == 0
    datasource_config["name"] = datasource_name
    context.add_datasource(**datasource_config.to_dict())

    # ensure datasource is accessible
    assert len(context.datasources) == 1
    assert datasource_name in context.datasources
    assert datasource_name in context.config.datasources

    context.delete_datasource(datasource_name)

    # ensure deleted
    assert len(context.datasources) == 0
    assert datasource_name not in context.datasources
    assert datasource_name not in context.config.datasources
