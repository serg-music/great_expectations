from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Iterator, List, cast
from unittest import mock

import pytest

import great_expectations.exceptions as ge_exceptions
import great_expectations.execution_engine.sparkdf_execution_engine
from great_expectations.core.util import GCSUrl
from great_expectations.experimental.datasources import (
    SparkGoogleCloudStorageDatasource,
)
from great_expectations.experimental.datasources.data_asset.data_connector import (
    GoogleCloudStorageDataConnector,
)
from great_expectations.experimental.datasources.file_path_data_asset import (
    _FilePathDataAsset,
)
from great_expectations.experimental.datasources.interfaces import TestConnectionError
from great_expectations.experimental.datasources.spark_file_path_datasource import (
    CSVAsset,
)

logger = logging.getLogger(__file__)


try:
    from google.cloud import storage
    from google.cloud.storage import Client as GCSClient
except ImportError:
    storage = None
    GCSClient = None
    logger.debug(
        "Unable to load GoogleCloudStorage connection object; install optional Google dependency for support"
    )


class MockGCSClient:
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def list_blobs(
        self,
        bucket_or_name,
        max_results=None,
        prefix=None,
        delimiter=None,
        **kwargs,
    ) -> Iterator:
        return iter([])


def _build_spark_gcs_datasource(
    gcs_options: Dict[str, Any] | None = None
) -> SparkGoogleCloudStorageDatasource:
    gcs_client: GCSClient = cast(GCSClient, MockGCSClient())
    spark_gcs_datasource = SparkGoogleCloudStorageDatasource(
        name="spark_gcs_datasource",
        bucket_or_name="test_bucket",
        gcs_options=gcs_options or {},
    )
    spark_gcs_datasource._gcs_client = gcs_client
    return spark_gcs_datasource


@pytest.fixture
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
def spark_gcs_datasource() -> SparkGoogleCloudStorageDatasource:
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource = (
        _build_spark_gcs_datasource()
    )
    return spark_gcs_datasource


@pytest.fixture
def object_keys() -> List[str]:
    return [
        "alex_20200809_1000.csv",
        "eugene_20200809_1500.csv",
        "james_20200811_1009.csv",
        "abe_20200809_1040.csv",
        "will_20200809_1002.csv",
        "james_20200713_1567.csv",
        "eugene_20201129_1900.csv",
        "will_20200810_1001.csv",
        "james_20200810_1003.csv",
        "alex_20200819_1300.csv",
    ]


@pytest.fixture
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
def csv_asset(
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
) -> _FilePathDataAsset:
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )
    return asset


@pytest.fixture
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
def bad_regex_config(csv_asset: CSVAsset) -> tuple[re.Pattern, str]:
    regex = re.compile(
        r"(?P<name>.+)_(?P<ssn>\d{9})_(?P<timestamp>.+)_(?P<price>\d{4})\.csv"
    )
    data_connector: GoogleCloudStorageDataConnector = cast(
        GoogleCloudStorageDataConnector, csv_asset._data_connector
    )
    test_connection_error_message = f"""No file in bucket "{csv_asset.datasource.bucket_or_name}" with prefix "{data_connector._prefix}" matched regular expressions pattern "{regex.pattern}" using delimiter "{data_connector._delimiter}" for DataAsset "{csv_asset.name}"."""
    return regex, test_connection_error_message


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
def test_construct_spark_gcs_datasource_without_gcs_options():
    google_cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not google_cred_file:
        pytest.skip('No "GOOGLE_APPLICATION_CREDENTIALS" environment variable found.')

    spark_gcs_datasource = SparkGoogleCloudStorageDatasource(
        name="spark_gcs_datasource",
        bucket_or_name="test_bucket",
        gcs_options={},
    )
    gcs_client: GCSClient = spark_gcs_datasource._get_gcs_client()
    assert gcs_client is not None
    assert spark_gcs_datasource.name == "spark_gcs_datasource"


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.oauth2.service_account.Credentials.from_service_account_file")
@mock.patch("google.cloud.storage.Client")
def test_construct_spark_gcs_datasource_with_filename_in_gcs_options(
    mock_gcs_client, mock_gcs_service_account_credentials, mock_list_keys
):
    spark_gcs_datasource = SparkGoogleCloudStorageDatasource(
        name="spark_gcs_datasource",
        bucket_or_name="test_bucket",
        gcs_options={
            "filename": "my_filename.csv",
        },
    )
    gcs_client: GCSClient = spark_gcs_datasource._get_gcs_client()
    assert gcs_client is not None
    assert spark_gcs_datasource.name == "spark_gcs_datasource"


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.oauth2.service_account.Credentials.from_service_account_info")
@mock.patch("google.cloud.storage.Client")
def test_construct_spark_gcs_datasource_with_info_in_gcs_options(
    mock_gcs_client, mock_gcs_service_account_credentials, mock_list_keys
):
    spark_gcs_datasource = SparkGoogleCloudStorageDatasource(
        name="spark_gcs_datasource",
        bucket_or_name="test_bucket",
        gcs_options={
            "info": "{my_csv: my_content,}",
        },
    )
    gcs_client: GCSClient = spark_gcs_datasource._get_gcs_client()
    assert gcs_client is not None
    assert spark_gcs_datasource.name == "spark_gcs_datasource"


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_add_csv_asset_to_datasource(
    mock_gcs_client,
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",
    )
    assert asset.name == "csv_asset"
    assert asset.batching_regex.match("random string") is None
    assert asset.batching_regex.match("alex_20200819_13D0.csv") is None
    m1 = asset.batching_regex.match("alex_20200819_1300.csv")
    assert m1 is not None


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_construct_csv_asset_directly(
    mock_gcs_client, mock_list_keys, object_keys: List[str]
):
    mock_list_keys.return_value = object_keys
    asset = CSVAsset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",  # type: ignore[arg-type]
    )
    assert asset.name == "csv_asset"
    assert asset.batching_regex.match("random string") is None
    assert asset.batching_regex.match("alex_20200819_13D0.csv") is None
    m1 = asset.batching_regex.match("alex_20200819_1300.csv")
    assert m1 is not None


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_csv_asset_with_regex_unnamed_parameters(
    mock_gcs_client,
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",
    )
    options = asset.batch_request_options_template()
    assert options == {
        "path": None,
        "batch_request_param_1": None,
        "batch_request_param_2": None,
        "batch_request_param_3": None,
    }


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_csv_asset_with_regex_named_parameters(
    mock_gcs_client,
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )
    options = asset.batch_request_options_template()
    assert options == {"path": None, "name": None, "timestamp": None, "price": None}


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_csv_asset_with_some_regex_named_parameters(
    mock_gcs_client,
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(.+)_(?P<price>\d{4})\.csv",
    )
    options = asset.batch_request_options_template()
    assert options == {
        "path": None,
        "name": None,
        "batch_request_param_2": None,
        "price": None,
    }


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
@mock.patch(
    "great_expectations.experimental.datasources.data_asset.data_connector.google_cloud_storage_data_connector.list_gcs_keys"
)
@mock.patch("google.cloud.storage.Client")
def test_csv_asset_with_non_string_regex_named_parameters(
    mock_gcs_client,
    mock_list_keys,
    object_keys: List[str],
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    mock_list_keys.return_value = object_keys
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(?P<price>\d{4})\.csv",
    )
    with pytest.raises(ge_exceptions.InvalidBatchRequestError):
        # price is an int which will raise an error
        asset.build_batch_request(
            {"name": "alex", "timestamp": "1234567890", "price": 1300}
        )


@pytest.mark.integration
@pytest.mark.xfail(
    reason="Accessing objects on google.cloud.storage using Spark is not working, due to local credentials issues (this test is conducted using Jupyter notebook manually)."
)
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
def test_get_batch_list_from_fully_specified_batch_request(
    monkeypatch: pytest.MonkeyPatch,
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
):
    gcs_client: GCSClient = cast(GCSClient, MockGCSClient())

    def instantiate_gcs_client_spy(self) -> None:
        self._gcs = gcs_client

    monkeypatch.setattr(
        great_expectations.execution_engine.sparkdf_execution_engine.SparkDFExecutionEngine,
        "_instantiate_s3_client",
        instantiate_gcs_client_spy,
        raising=True,
    )
    asset = spark_gcs_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )

    request = asset.build_batch_request(
        {"name": "alex", "timestamp": "20200819", "price": "1300"}
    )
    batches = asset.get_batch_list_from_batch_request(request)
    assert len(batches) == 1
    batch = batches[0]
    assert batch.batch_request.datasource_name == spark_gcs_datasource.name
    assert batch.batch_request.data_asset_name == asset.name
    assert batch.batch_request.options == {
        "path": "alex_20200819_1300.csv",
        "name": "alex",
        "timestamp": "20200819",
        "price": "1300",
    }
    assert batch.metadata == {
        "path": "alex_20200819_1300.csv",
        "name": "alex",
        "timestamp": "20200819",
        "price": "1300",
    }
    assert (
        batch.id
        == "spark_gcs_datasource-csv_asset-name_alex-timestamp_20200819-price_1300"
    )

    request = asset.build_batch_request({"name": "alex"})
    batches = asset.get_batch_list_from_batch_request(request)
    assert len(batches) == 2


@pytest.mark.integration
@pytest.mark.skipif(
    storage is None, reason='Could not import "storage" from google.cloud'
)
def test_test_connection_failures(
    spark_gcs_datasource: SparkGoogleCloudStorageDatasource,
    bad_regex_config: tuple[re.Pattern, str],
):
    regex, test_connection_error_message = bad_regex_config
    csv_asset = CSVAsset(
        name="csv_asset",
        batching_regex=regex,
    )
    csv_asset._datasource = spark_gcs_datasource
    spark_gcs_datasource.assets = {"csv_asset": csv_asset}
    csv_asset._data_connector = GoogleCloudStorageDataConnector(
        datasource_name=spark_gcs_datasource.name,
        data_asset_name=csv_asset.name,
        batching_regex=re.compile(regex),
        gcs_client=spark_gcs_datasource._gcs_client,
        bucket_or_name=spark_gcs_datasource.bucket_or_name,
        file_path_template_map_fn=GCSUrl.OBJECT_URL_TEMPLATE.format,
    )
    csv_asset._test_connection_error_message = test_connection_error_message

    with pytest.raises(TestConnectionError) as e:
        spark_gcs_datasource.test_connection()

    assert str(e.value) == str(test_connection_error_message)
