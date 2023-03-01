from ruamel import yaml

import great_expectations as gx
from great_expectations.core.batch import BatchRequest, RuntimeBatchRequest

CONNECTION_STRING = "mysql+pymysql://root@localhost/test_ci"

# This utility is not for general use. It is only to support testing.
from tests.test_utils import load_data_into_test_database

load_data_into_test_database(
    table_name="taxi_data",
    csv_path="./data/yellow_tripdata_sample_2019-01.csv",
    connection_string=CONNECTION_STRING,
)

context = gx.get_context()

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/mysql_python_example.py datasource config">
datasource_config = {
    "name": "my_mysql_datasource",
    "class_name": "Datasource",
    "execution_engine": {
        "class_name": "SqlAlchemyExecutionEngine",
        "connection_string": "mysql+pymysql://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>",
    },
    "data_connectors": {
        "default_runtime_data_connector_name": {
            "class_name": "RuntimeDataConnector",
            "batch_identifiers": ["default_identifier_name"],
        },
        "default_inferred_data_connector_name": {
            "class_name": "InferredAssetSqlDataConnector",
            "include_schema_name": True,
        },
    },
}
# </snippet>

# Please note this override is only to provide good UX for docs and tests.
# In normal usage you'd set your path directly in the yaml above.
datasource_config["execution_engine"]["connection_string"] = CONNECTION_STRING

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/mysql_python_example.py test datasource config">
context.test_yaml_config(yaml.dump(datasource_config))
# </snippet>

# <snippet name="tests/integration/docusaurus/connecting_to_your_data/database/mysql_python_example.py add datasource config">
context.add_datasource(**datasource_config)
# </snippet>

# Here is a RuntimeBatchRequest using a query
batch_request = RuntimeBatchRequest(
    datasource_name="my_mysql_datasource",
    data_connector_name="default_runtime_data_connector_name",
    data_asset_name="default_name",  # this can be anything that identifies this data
    runtime_parameters={"query": "SELECT * from test_ci.taxi_data LIMIT 10"},
    batch_identifiers={"default_identifier_name": "default_identifier"},
    batch_spec_passthrough={
        "reader_options": {
            "pool_size": 5
        }  # NOTE: create_engine arguments may be passed here
    },
)
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)

# Here is a BatchRequest naming a table
batch_request = BatchRequest(
    datasource_name="my_mysql_datasource",
    data_connector_name="default_inferred_data_connector_name",
    data_asset_name="test_ci.taxi_data",  # this is the name of the table you want to retrieve
)
context.add_or_update_expectation_suite(expectation_suite_name="test_suite")
validator = context.get_validator(
    batch_request=batch_request, expectation_suite_name="test_suite"
)
print(validator.head())

# NOTE: The following code is only for testing and can be ignored by users.
assert isinstance(validator, gx.validator.validator.Validator)
assert [ds["name"] for ds in context.list_datasources()] == ["my_mysql_datasource"]
assert (
    "test_ci.taxi_data"
    in context.get_available_data_asset_names()["my_mysql_datasource"][
        "default_inferred_data_connector_name"
    ]
)
