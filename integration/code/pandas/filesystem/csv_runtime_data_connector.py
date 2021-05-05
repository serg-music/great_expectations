import great_expectations as ge
from great_expectations.cli.datasource import sanitize_yaml_and_save_datasource
from great_expectations.core.batch import RuntimeBatchRequest

context = ge.DataContext(context_root_dir="../../../fixtures/runtime_data_taxi_monthly/great_expectations/", )
# context = ge.get_context()

datasource_yaml = f"""
name: taxi_datasource_with_runtime_data_connector
class_name: Datasource
module_name: great_expectations.datasource
execution_engine:
  module_name: great_expectations.execution_engine
  class_name: PandasExecutionEngine
data_connectors:
    default_runtime_data_connector_name:
        class_name: RuntimeDataConnector
        batch_identifiers:
            - default_identifier_name
"""

sanitize_yaml_and_save_datasource(context, datasource_yaml, overwrite_existing=True)

batch_request = RuntimeBatchRequest(
    datasource_name="taxi_datasource_with_runtime_data_connector",
    data_connector_name="default_runtime_data_connector_name",
    data_asset_name="default_name",  # this can be anything that identifies this data_asset for you
    runtime_parameters={
        "path": "./data/reports/yellow_tripdata_sample_2019-01.csv"
    },
    batch_identifiers={"default_identifier_name": "something_something"},
)

batch_request.runtime_parameters["path"] = "../../../fixtures/data/reports/yellow_tripdata_sample_2019-01.csv"

batch = context.get_batch(batch_request=batch_request)

# this may not be the right test at the end.
print(batch.__str__())