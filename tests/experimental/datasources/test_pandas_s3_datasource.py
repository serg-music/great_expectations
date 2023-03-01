from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, List, cast

import pandas as pd
import pytest
from moto import mock_s3

import great_expectations.exceptions as ge_exceptions
from great_expectations.core.util import S3Url
from great_expectations.experimental.datasources import PandasS3Datasource
from great_expectations.experimental.datasources.data_asset.data_connector import (
    S3DataConnector,
)
from great_expectations.experimental.datasources.dynamic_pandas import PANDAS_VERSION
from great_expectations.experimental.datasources.file_path_data_asset import (
    _FilePathDataAsset,
)
from great_expectations.experimental.datasources.interfaces import TestConnectionError
from great_expectations.experimental.datasources.pandas_file_path_datasource import (
    CSVAsset,
)

if TYPE_CHECKING:
    from botocore.client import BaseClient


logger = logging.getLogger(__file__)


try:
    import boto3
except ImportError:
    logger.debug("Unable to load boto3; install optional boto3 dependency for support.")
    boto3 = None


# apply markers to entire test module
pytestmark = [
    pytest.mark.skipif(
        PANDAS_VERSION < 1.2, reason=f"ZEP pandas not supported on {PANDAS_VERSION}"
    )
]


@pytest.fixture()
def aws_region_name() -> str:
    return "us-east-1"


@pytest.fixture()
def aws_s3_bucket_name() -> str:
    return "test_bucket"


@pytest.fixture(scope="function")
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture
def s3_mock(aws_credentials, aws_region_name: str) -> BaseClient:
    with mock_s3():
        client = boto3.client("s3", region_name=aws_region_name)
        yield client


@pytest.fixture
def s3_bucket(s3_mock: BaseClient, aws_s3_bucket_name: str) -> str:
    bucket_name: str = aws_s3_bucket_name
    s3_mock.create_bucket(Bucket=bucket_name)
    return bucket_name


@pytest.fixture
def pandas_s3_datasource(s3_mock, s3_bucket: str) -> PandasS3Datasource:
    test_df: pd.DataFrame = pd.DataFrame(data={"col1": [1, 2], "col2": [3, 4]})

    keys: List[str] = [
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

    for key in keys:
        s3_mock.put_object(
            Bucket=s3_bucket,
            Body=test_df.to_csv(index=False).encode("utf-8"),
            Key=key,
        )

    return PandasS3Datasource(
        name="pandas_s3_datasource",
        bucket=s3_bucket,
    )


@pytest.fixture
def csv_asset(pandas_s3_datasource: PandasS3Datasource) -> _FilePathDataAsset:
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )
    return asset


@pytest.fixture
def bad_regex_config(csv_asset: CSVAsset) -> tuple[re.Pattern, str]:  # type: ignore[valid-type]
    regex = re.compile(
        r"(?P<name>.+)_(?P<ssn>\d{9})_(?P<timestamp>.+)_(?P<price>\d{4})\.csv"
    )
    data_connector: S3DataConnector = cast(S3DataConnector, csv_asset._data_connector)  # type: ignore[attr-defined]
    test_connection_error_message = f"""No file in bucket "{csv_asset.datasource.bucket}" with prefix "{data_connector._prefix}" matched regular expressions pattern "{regex.pattern}" using delimiter "{data_connector._delimiter}" for DataAsset "{csv_asset.name}"."""  # type: ignore[attr-defined]
    return regex, test_connection_error_message


@pytest.mark.integration
def test_construct_pandas_s3_datasource(pandas_s3_datasource: PandasS3Datasource):
    assert pandas_s3_datasource.name == "pandas_s3_datasource"


@pytest.mark.integration
def test_add_csv_asset_to_datasource(pandas_s3_datasource: PandasS3Datasource):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",
    )
    assert asset.name == "csv_asset"  # type: ignore[attr-defined]
    assert asset.batching_regex.match("random string") is None  # type: ignore[attr-defined]
    assert asset.batching_regex.match("alex_20200819_13D0.csv") is None  # type: ignore[attr-defined]
    m1 = asset.batching_regex.match("alex_20200819_1300.csv")  # type: ignore[attr-defined]
    assert m1 is not None


@pytest.mark.integration
def test_construct_csv_asset_directly():
    # noinspection PyTypeChecker
    asset = CSVAsset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",
    )
    assert asset.name == "csv_asset"
    assert asset.batching_regex.match("random string") is None
    assert asset.batching_regex.match("alex_20200819_13D0.csv") is None
    m1 = asset.batching_regex.match("alex_20200819_1300.csv")
    assert m1 is not None


@pytest.mark.integration
def test_csv_asset_with_regex_unnamed_parameters(
    pandas_s3_datasource: PandasS3Datasource,
):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(\d{4})\.csv",
    )
    options = asset.batch_request_options_template()  # type: ignore[attr-defined]
    assert options == {
        "path": None,
        "batch_request_param_1": None,
        "batch_request_param_2": None,
        "batch_request_param_3": None,
    }


@pytest.mark.integration
def test_csv_asset_with_regex_named_parameters(
    pandas_s3_datasource: PandasS3Datasource,
):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )
    options = asset.batch_request_options_template()  # type: ignore[attr-defined]
    assert options == {"path": None, "name": None, "timestamp": None, "price": None}


@pytest.mark.integration
def test_csv_asset_with_some_regex_named_parameters(
    pandas_s3_datasource: PandasS3Datasource,
):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(.+)_(?P<price>\d{4})\.csv",
    )
    options = asset.batch_request_options_template()  # type: ignore[attr-defined]
    assert options == {
        "path": None,
        "name": None,
        "batch_request_param_2": None,
        "price": None,
    }


@pytest.mark.integration
def test_csv_asset_with_non_string_regex_named_parameters(
    pandas_s3_datasource: PandasS3Datasource,
):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(.+)_(.+)_(?P<price>\d{4})\.csv",
    )
    with pytest.raises(ge_exceptions.InvalidBatchRequestError):
        # price is an int which will raise an error
        asset.build_batch_request(  # type: ignore[attr-defined]
            {"name": "alex", "timestamp": "1234567890", "price": 1300}
        )


@pytest.mark.integration
def test_get_batch_list_from_fully_specified_batch_request(
    pandas_s3_datasource: PandasS3Datasource,
):
    asset = pandas_s3_datasource.add_csv_asset(
        name="csv_asset",
        batching_regex=r"(?P<name>.+)_(?P<timestamp>.+)_(?P<price>\d{4})\.csv",
    )

    request = asset.build_batch_request(  # type: ignore[attr-defined]
        {"name": "alex", "timestamp": "20200819", "price": "1300"}
    )
    batches = asset.get_batch_list_from_batch_request(request)  # type: ignore[attr-defined]
    assert len(batches) == 1
    batch = batches[0]
    assert batch.batch_request.datasource_name == pandas_s3_datasource.name
    assert batch.batch_request.data_asset_name == asset.name  # type: ignore[attr-defined]
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
        == "pandas_s3_datasource-csv_asset-name_alex-timestamp_20200819-price_1300"
    )

    request = asset.build_batch_request({"name": "alex"})  # type: ignore[attr-defined]
    batches = asset.get_batch_list_from_batch_request(request)  # type: ignore[attr-defined]
    assert len(batches) == 2


@pytest.mark.integration
def test_test_connection_failures(
    s3_mock,
    pandas_s3_datasource: PandasS3Datasource,
    bad_regex_config: tuple[re.Pattern, str],
):
    regex, test_connection_error_message = bad_regex_config
    csv_asset = CSVAsset(
        name="csv_asset",
        batching_regex=regex,
    )
    csv_asset._datasource = pandas_s3_datasource
    pandas_s3_datasource.assets = {"csv_asset": csv_asset}
    csv_asset._data_connector = S3DataConnector(
        datasource_name=pandas_s3_datasource.name,
        data_asset_name=csv_asset.name,
        batching_regex=re.compile(regex),
        s3_client=s3_mock,
        bucket=pandas_s3_datasource.bucket,
        file_path_template_map_fn=S3Url.OBJECT_URL_TEMPLATE.format,
    )
    csv_asset._test_connection_error_message = test_connection_error_message

    with pytest.raises(TestConnectionError) as e:
        pandas_s3_datasource.test_connection()

    assert str(e.value) == str(test_connection_error_message)
