# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py imports">
from ruamel import yaml

import great_expectations as gx
from great_expectations.core.batch import BatchRequest, RuntimeBatchRequest

# </snippet>

CONNECTION_STRING = "sqlite:///data/yellow_tripdata.db"

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py get_context">
context = gx.get_context()
# </snippet>

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py datasource_yaml">
datasource_yaml = f"""
name: my_sqlite_datasource
class_name: Datasource
execution_engine:
  class_name: SqlAlchemyExecutionEngine
  connection_string: sqlite://<PATH_TO_DB_FILE>
data_connectors:
   default_runtime_data_connector_name:
       class_name: RuntimeDataConnector
       batch_identifiers:
           - default_identifier_name
   default_inferred_data_connector_name:
       class_name: InferredAssetSqlDataConnector
       include_schema_name: true
"""
# </snippet>

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your path directly in the yaml above.
datasource_yaml = datasource_yaml.replace(
    "sqlite://<PATH_TO_DB_FILE>",
    CONNECTION_STRING,
)
# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py test_yaml_config">
context.test_yaml_config(datasource_yaml)
# </snippet>

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py add_datasource">
context.add_datasource(**yaml.load(datasource_yaml))
# </snippet>

# Here is a RuntimeBatchRequest using a query
# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/sqlite_yaml_example.py query batch_request">
batch_request = RuntimeBatchRequest(
    datasource_name="my_sqlite_datasource",
    data_connector_name="default_runtime_data_connector_name",
    data_asset_name="default_name",  # this can be anything that identifies this data
    runtime_parameters={
        "query": "SELECT * from main.yellow_tripdata_sample_2019_01 LIMIT 10"
    },
    batch_identifiers={"default_identifier_name": "default_identifier"},
)
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())
# </snippet>

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)

# Here is a BatchRequest naming a table
batch_request = BatchRequest(
    datasource_name="my_sqlite_datasource",
    data_connector_name="default_inferred_data_connector_name",
    data_asset_name="main.yellow_tripdata_sample_2019_01",  # this is the name of the table you want to retrieve
)
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)
assert [ds["name"] for ds in context.list_datasources()] == ["my_sqlite_datasource"]
assert "main.yellow_tripdata_sample_2019_01" in set(
    context.get_available_data_asset_names()["my_sqlite_datasource"][
        "default_inferred_data_connector_name"
    ]
)
