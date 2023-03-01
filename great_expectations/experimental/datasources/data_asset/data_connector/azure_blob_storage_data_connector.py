from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Callable, List, Optional

from great_expectations.core.batch_spec import AzureBatchSpec, PathBatchSpec
from great_expectations.datasource.data_connector.util import (
    list_azure_keys,
    sanitize_prefix,
)
from great_expectations.experimental.datasources.data_asset.data_connector import (
    FilePathDataConnector,
)

if TYPE_CHECKING:
    from azure.storage.blob import BlobServiceClient

    from great_expectations.core.batch import BatchDefinition


logger = logging.getLogger(__name__)


class AzureBlobStorageDataConnector(FilePathDataConnector):
    """Extension of FilePathDataConnector used to connect to Microsoft Azure Blob Storage (ABS).

    Args:
        datasource_name: The name of the Datasource associated with this DataConnector instance
        data_asset_name: The name of the DataAsset using this DataConnector instance
        batching_regex: A regex pattern for partitioning data references
        azure_client: Reference to instantiated Microsoft Azure Blob Storage client handle
        account_name (str): account name for Microsoft Azure Blob Storage
        container (str): container name for Microsoft Azure Blob Storage
        name_starts_with (str): Microsoft Azure Blob Storage prefix
        delimiter (str): Microsoft Azure Blob Storage delimiter
        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # sorters (list): optional list of sorters for sorting data_references
        file_path_template_map_fn: Format function mapping path to fully-qualified resource on network file storage
        # TODO: <Alex>ALEX</Alex>
    """

    def __init__(
        self,
        datasource_name: str,
        data_asset_name: str,
        batching_regex: re.Pattern,
        azure_client: BlobServiceClient,
        account_name: str,
        container: str,
        name_starts_with: str = "",
        delimiter: str = "/",
        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # sorters: Optional[list] = None,
        # TODO: <Alex>ALEX</Alex>
        file_path_template_map_fn: Optional[Callable] = None,
    ) -> None:
        self._azure_client: BlobServiceClient = azure_client

        self._account_name = account_name
        self._container = container
        self._name_starts_with = sanitize_prefix(name_starts_with)
        self._delimiter = delimiter

        super().__init__(
            datasource_name=datasource_name,
            data_asset_name=data_asset_name,
            batching_regex=batching_regex,
            # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
            # TODO: <Alex>ALEX</Alex>
            # sorters=sorters,
            # TODO: <Alex>ALEX</Alex>
            file_path_template_map_fn=file_path_template_map_fn,
        )

    def build_batch_spec(self, batch_definition: BatchDefinition) -> AzureBatchSpec:
        """
        Build BatchSpec from batch_definition by calling DataConnector's build_batch_spec function.

        Args:
            batch_definition (BatchDefinition): to be used to build batch_spec

        Returns:
            BatchSpec built from batch_definition
        """
        batch_spec: PathBatchSpec = super().build_batch_spec(
            batch_definition=batch_definition
        )
        return AzureBatchSpec(batch_spec)

    # Interface Method
    def get_data_references(self) -> List[str]:
        query_options: dict = {
            "container": self._container,
            "name_starts_with": self._name_starts_with,
            "delimiter": self._delimiter,
        }
        path_list: List[str] = list_azure_keys(
            azure_client=self._azure_client,
            query_options=query_options,
            recursive=False,
        )
        return path_list

    # Interface Method
    def _get_full_file_path(self, path: str) -> str:
        if self._file_path_template_map_fn is None:
            raise ValueError(
                f"""Converting file paths to fully-qualified object references for "{self.__class__.__name__}" \
requires "file_path_template_map_fn: Callable" to be set.
"""
            )

        template_arguments: dict = {
            "account_name": self._account_name,
            "container": self._container,
            "path": path,
        }

        return self._file_path_template_map_fn(**template_arguments)
