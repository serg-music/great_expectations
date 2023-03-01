from typing import List

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py imports for spark data context">
from ruamel import yaml

import great_expectations as gx
from great_expectations.core.batch import Batch, BatchRequest, RuntimeBatchRequest

# </snippet>
from great_expectations.data_context.types.base import (
    DataContextConfig,
    InMemoryStoreBackendDefaults,
)
from great_expectations.util import get_context

# NOTE: InMemoryStoreBackendDefaults SHOULD NOT BE USED in normal settings. You
# may experience data loss as it persists nothing. It is used here for testing.
# Please refer to docs to learn how to instantiate your DataContext.
store_backend_defaults = InMemoryStoreBackendDefaults()
data_context_config = DataContextConfig(
    store_backend_defaults=store_backend_defaults,
    checkpoint_store_name=store_backend_defaults.checkpoint_store_name,
)
context = get_context(project_config=data_context_config)

datasource_yaml = rf"""
# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py datasource config">
name: my_s3_datasource
class_name: Datasource
execution_engine:
    class_name: SparkDFExecutionEngine
data_connectors:
    default_runtime_data_connector_name:
        class_name: RuntimeDataConnector
        batch_identifiers:
            - default_identifier_name
    default_inferred_data_connector_name:
        class_name: InferredAssetS3DataConnector
        bucket: <YOUR_S3_BUCKET_HERE>
        prefix: <BUCKET_PATH_TO_DATA>
        default_regex:
            pattern: (.*)\.csv
            group_names:
                - data_asset_name
# </snippet>
"""

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your path directly in the yaml above.
datasource_yaml = datasource_yaml.replace(
    "<YOUR_S3_BUCKET_HERE>", "superconductive-public"
)
datasource_yaml = datasource_yaml.replace(
    "<BUCKET_PATH_TO_DATA>", "data/taxi_yellow_tripdata_samples/"
)

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py test datasource config">
context.test_yaml_config(datasource_yaml)
# </snippet>

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py add datasource config">
context.add_datasource(**yaml.load(datasource_yaml))
# </snippet>

# Here is a RuntimeBatchRequest using a path to a single CSV file
# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py batch request 1">
batch_request = RuntimeBatchRequest(
    datasource_name="my_s3_datasource",
    data_connector_name="default_runtime_data_connector_name",
    data_asset_name="<YOUR_MEANGINGFUL_NAME>",  # this can be anything that identifies this data_asset for you
    runtime_parameters={"path": "<PATH_TO_YOUR_DATA_HERE>"},  # Add your S3 path here.
    batch_identifiers={"default_identifier_name": "default_identifier"},
)
# </snippet>

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your path directly in the BatchRequest above.
batch_request.runtime_parameters[
    "path"
] = "s3a://superconductive-public/data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_2019-01.csv"

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py get validator 1">
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())
# </snippet>

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)

# Here is a BatchRequest naming a data_asset
# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py batch request 2">
batch_request = BatchRequest(
    datasource_name="my_s3_datasource",
    data_connector_name="default_inferred_data_connector_name",
    data_asset_name="<YOUR_DATA_ASSET_NAME>",
    batch_spec_passthrough={"reader_method": "csv", "reader_options": {"header": True}},
)
# </snippet>

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your data asset name directly in the BatchRequest above.
batch_request.data_asset_name = (
    "data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_2019-01"
)

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/s3/spark/inferred_and_runtime_yaml_example.py get validator 2">
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())
# </snippet>

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)
assert [ds["name"] for ds in context.list_datasources()] == ["my_s3_datasource"]
assert set(
    context.get_available_data_asset_names()["my_s3_datasource"][
        "default_inferred_data_connector_name"
    ]
) == {
    "data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_2019-01",
    "data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_2019-02",
    "data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_2019-03",
}


batch_list: List[Batch] = context.get_batch_list(batch_request=batch_request)
assert len(batch_list) == 1

batch: Batch = batch_list[0]
assert batch.data.dataframe.count() == 10000
