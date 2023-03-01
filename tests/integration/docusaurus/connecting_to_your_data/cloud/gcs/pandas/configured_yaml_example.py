from typing import List

from ruamel import yaml

import great_expectations as gx
from great_expectations.core.batch import Batch, BatchRequest

context = gx.get_context()

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/gcs/pandas/configured_yaml_example.py datasource config">
datasource_yaml = f"""
name: my_gcs_datasource
class_name: Datasource
execution_engine:
    class_name: PandasExecutionEngine
data_connectors:
    configured_data_connector_name:
        class_name: ConfiguredAssetGCSDataConnector
        bucket_or_name: <YOUR_GCS_BUCKET_HERE>
        prefix: <BUCKET_PATH_TO_DATA>
        default_regex:
            pattern: data/taxi_yellow_tripdata_samples/yellow_tripdata_sample_(\\d{{4}})-(\\d{{2}})\\.csv
            group_names:
                - year
                - month
        assets:
            taxi_data:
"""
# </snippet>

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your path directly in the yaml above.
datasource_yaml = datasource_yaml.replace("<YOUR_GCS_BUCKET_HERE>", "test_docs_data")
datasource_yaml = datasource_yaml.replace(
    "<BUCKET_PATH_TO_DATA>", "data/taxi_yellow_tripdata_samples/"
)

context.test_yaml_config(datasource_yaml)

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/cloud/gcs/pandas/configured_yaml_example.py test datasource config">
context.add_datasource(**yaml.load(datasource_yaml))
# </snippet>

# Here is a BatchRequest naming a data_asset
batch_request = BatchRequest(
    datasource_name="my_gcs_datasource",
    data_connector_name="configured_data_connector_name",
    data_asset_name="<YOUR_DATA_ASSET_NAME>",
)

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your data asset name directly in the BatchRequest above.
batch_request.data_asset_name = "taxi_data"

context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())


# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)
assert [ds["name"] for ds in context.list_datasources()] == ["my_gcs_datasource"]
assert set(
    context.get_available_data_asset_names()["my_gcs_datasource"][
        "configured_data_connector_name"
    ]
) == {"taxi_data"}

batch_list: List[Batch] = context.get_batch_list(batch_request=batch_request)
assert len(batch_list) == 3

batch: Batch = batch_list[0]
assert batch.data.dataframe.shape[0] == 10000
