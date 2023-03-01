from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import pydantic
from typing_extensions import Literal

from great_expectations.core.util import AzureUrl
from great_expectations.experimental.datasources import _SparkFilePathDatasource
from great_expectations.experimental.datasources.data_asset.data_connector import (
    AzureBlobStorageDataConnector,
    DataConnector,
)
from great_expectations.experimental.datasources.interfaces import TestConnectionError
from great_expectations.experimental.datasources.spark_datasource import (
    SparkDatasourceError,
)
from great_expectations.experimental.datasources.spark_file_path_datasource import (
    CSVAsset,
)

if TYPE_CHECKING:
    from great_expectations.experimental.datasources.interfaces import (
        BatchSorter,
        BatchSortersDefinition,
    )


logger = logging.getLogger(__name__)


ABS_IMPORTED = False
try:
    from azure.storage.blob import (
        BlobServiceClient,
    )

    ABS_IMPORTED = True
except ImportError:
    pass


class SparkAzureBlobStorageDatasourceError(SparkDatasourceError):
    pass


class SparkAzureBlobStorageDatasource(_SparkFilePathDatasource):
    # instance attributes
    type: Literal["spark_abs"] = "spark_abs"

    # Azure Blob Storage specific attributes
    azure_options: Dict[str, Any] = {}

    _account_name: str = pydantic.PrivateAttr(default="")
    _azure_client: Union[BlobServiceClient, None] = pydantic.PrivateAttr(default=None)

    def _get_azure_client(self) -> BlobServiceClient:
        azure_client: Union[BlobServiceClient, None] = self._azure_client
        if not azure_client:
            # Thanks to schema validation, we are guaranteed to have one of `conn_str` or `account_url` to
            # use in authentication (but not both). If the format or content of the provided keys is invalid,
            # the assignment of `self._account_name` and `self._azure_client` will fail and an error will be raised.
            conn_str: str | None = self.azure_options.get("conn_str")
            account_url: str | None = self.azure_options.get("account_url")
            if not bool(conn_str) ^ bool(account_url):
                raise SparkAzureBlobStorageDatasourceError(
                    "You must provide one of `conn_str` or `account_url` to the `azure_options` key in your config (but not both)"
                )

            # Validate that "azure" libararies were successfully imported and attempt to create "azure_client" handle.
            if ABS_IMPORTED:
                try:
                    if conn_str is not None:
                        self._account_name = re.search(  # type: ignore[union-attr]
                            r".*?AccountName=(.+?);.*?", conn_str
                        ).group(1)
                        azure_client = BlobServiceClient.from_connection_string(
                            **self.azure_options
                        )
                    elif account_url is not None:
                        self._account_name = re.search(  # type: ignore[union-attr]
                            r"(?:https?://)?(.+?).blob.core.windows.net", account_url
                        ).group(1)
                        azure_client = BlobServiceClient(**self.azure_options)
                except Exception as e:
                    # Failure to create "azure_client" is most likely due invalid "azure_options" dictionary.
                    raise SparkAzureBlobStorageDatasourceError(
                        f'Due to exception: "{str(e)}", "azure_client" could not be created.'
                    ) from e
            else:
                raise SparkAzureBlobStorageDatasourceError(
                    'Unable to create "SparkAzureBlobStorageDatasource" due to missing azure.storage.blob dependency.'
                )

            self._azure_client = azure_client

        return azure_client

    def test_connection(self, test_assets: bool = True) -> None:
        """Test the connection for the SparkAzureBlobStorageDatasource.

        Args:
            test_assets: If assets have been passed to the SparkAzureBlobStorageDatasource, whether to test them as well.

        Raises:
            TestConnectionError: If the connection test fails.
        """
        if self._azure_client is None:
            raise TestConnectionError(
                "Unable to load azure.storage.blob.BlobServiceClient (it is required for SparkAzureBlobStorageDatasource)."
            )

        if self.assets and test_assets:
            for asset in self.assets.values():
                asset.test_connection()

    def add_csv_asset(
        self,
        name: str,
        batching_regex: Union[re.Pattern, str],
        container: str,
        name_starts_with: str = "",
        delimiter: str = "/",
        order_by: Optional[BatchSortersDefinition] = None,
    ) -> CSVAsset:
        """Adds a CSV DataAsst to the present "SparkAzureBlobStorageDatasource" object.

        Args:
            name: The name of the CSV asset
            batching_regex: regex pattern that matches csv filenames that is used to label the batches
            container: container name for Microsoft Azure Blob Storage
            name_starts_with: Microsoft Azure Blob Storage object name prefix
            delimiter: Microsoft Azure Blob Storage object name delimiter
            order_by: sorting directive via either list[BatchSorter] or "{+|-}key" syntax: +/- (a/de)scending; + default
        """
        batching_regex_pattern: re.Pattern = self.parse_batching_regex_string(
            batching_regex=batching_regex
        )
        order_by_sorters: list[BatchSorter] = self.parse_order_by_sorters(
            order_by=order_by
        )

        asset = CSVAsset(
            name=name,
            batching_regex=batching_regex_pattern,
            order_by=order_by_sorters,
        )

        data_connector: DataConnector = AzureBlobStorageDataConnector(
            datasource_name=self.name,
            data_asset_name=name,
            batching_regex=batching_regex_pattern,
            azure_client=self._azure_client,
            account_name=self._account_name,
            container=container,
            name_starts_with=name_starts_with,
            delimiter=delimiter,
            file_path_template_map_fn=AzureUrl.AZURE_BLOB_STORAGE_HTTPS_URL_TEMPLATE.format,
        )
        test_connection_error_message: str = f"""No file belonging to account "{self._account_name}" in container "{container}" with prefix "{name_starts_with}" matched regular expressions pattern "{batching_regex_pattern.pattern}" using delimiter "{delimiter}" for DataAsset "{name}"."""
        return self.add_asset(
            asset=asset,
            data_connector=data_connector,
            test_connection_error_message=test_connection_error_message,
        )
