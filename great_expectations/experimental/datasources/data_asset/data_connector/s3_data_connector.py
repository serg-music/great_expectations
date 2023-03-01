from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Callable, List, Optional

from great_expectations.core.batch_spec import PathBatchSpec, S3BatchSpec
from great_expectations.datasource.data_connector.util import (
    list_s3_keys,
    sanitize_prefix_for_s3,
)
from great_expectations.experimental.datasources.data_asset.data_connector import (
    FilePathDataConnector,
)

if TYPE_CHECKING:
    from botocore.client import BaseClient

    from great_expectations.core.batch import BatchDefinition


logger = logging.getLogger(__name__)


class S3DataConnector(FilePathDataConnector):
    """Extension of FilePathDataConnector used to connect to S3.


    Args:
        datasource_name: The name of the Datasource associated with this DataConnector instance
        data_asset_name: The name of the DataAsset using this DataConnector instance
        s3_client: Reference to instantiated AWS S3 client handle
        bucket (str): bucket for S3
        batching_regex: A regex pattern for partitioning data references
        prefix (str): S3 prefix
        delimiter (str): S3 delimiter
        max_keys (int): S3 max_keys (default is 1000)
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
        s3_client: BaseClient,
        bucket: str,
        prefix: str = "",
        delimiter: str = "/",
        max_keys: int = 1000,
        # TODO: <Alex>ALEX_INCLUDE_SORTERS_FUNCTIONALITY_UNDER_PYDANTIC-MAKE_SURE_SORTER_CONFIGURATIONS_ARE_VALIDATED</Alex>
        # TODO: <Alex>ALEX</Alex>
        # sorters: Optional[list] = None,
        # TODO: <Alex>ALEX</Alex>
        file_path_template_map_fn: Optional[Callable] = None,
    ) -> None:
        self._s3_client: BaseClient = s3_client

        self._bucket: str = bucket
        self._prefix: str = sanitize_prefix_for_s3(prefix)
        self._delimiter: str = delimiter
        self._max_keys: int = max_keys

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

    def build_batch_spec(self, batch_definition: BatchDefinition) -> S3BatchSpec:
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
        return S3BatchSpec(batch_spec)

    # Interface Method
    def get_data_references(self) -> List[str]:
        query_options: dict = {
            "Bucket": self._bucket,
            "Prefix": self._prefix,
            "Delimiter": self._delimiter,
            "MaxKeys": self._max_keys,
        }
        path_list: List[str] = list(
            list_s3_keys(
                s3=self._s3_client,
                query_options=query_options,
                iterator_dict={},
                recursive=False,
            )
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
            "bucket": self._bucket,
            "path": path,
        }

        return self._file_path_template_map_fn(**template_arguments)
