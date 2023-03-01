"""
Test the expectation decorator's ability to substitute parameters
at evaluation time, and store parameters in expectation_suite
"""
import datetime
import json
from typing import Dict

import numpy as np
import pytest

from great_expectations.core import ExpectationConfiguration
from great_expectations.core.batch import BatchRequest
from great_expectations.data_asset import DataAsset
from great_expectations.exceptions import EvaluationParameterError
from great_expectations.execution_engine import ExecutionEngine
from great_expectations.expectations.expectation import Expectation
from great_expectations.expectations.registry import register_expectation
from great_expectations.self_check.util import expectationSuiteValidationResultSchema


@pytest.fixture
def data_asset():
    return DataAsset()


@pytest.fixture
def single_expectation_custom_data_asset():
    class SlimCustomDataAsset(DataAsset):
        @DataAsset.expectation("expectation_argument")
        def expect_nothing(self, expectation_argument):
            return {
                "success": True,
                "result": {"details": {"expectation_argument": expectation_argument}},
            }

    return SlimCustomDataAsset()


@pytest.fixture
def validator_with_titanic_1911_asset(
    titanic_pandas_data_context_with_v013_datasource_with_checkpoints_v1_with_empty_store_stats_enabled,
):
    class ExpectNothing(Expectation):
        success_keys = ("expectation_argument",)

        def _validate(
            self,
            configuration: ExpectationConfiguration,
            metrics: Dict,
            runtime_configuration: dict = None,
            execution_engine: ExecutionEngine = None,
        ):
            expectation_argument = configuration.kwargs.get("expectation_argument")
            return {
                "success": True,
                "result": {"details": {"expectation_argument": expectation_argument}},
            }

    register_expectation(ExpectNothing)

    titanic_pandas_data_context_with_v013_datasource_with_checkpoints_v1_with_empty_store_stats_enabled.add_expectation_suite(
        expectation_suite_name="titanic_1911_suite"
    )
    batch_request = BatchRequest(
        datasource_name="my_datasource",
        data_connector_name="my_basic_data_connector",
        data_asset_name="Titanic_1911",
    )
    return titanic_pandas_data_context_with_v013_datasource_with_checkpoints_v1_with_empty_store_stats_enabled.get_validator(
        batch_request=batch_request, expectation_suite_name="titanic_1911_suite"
    )


def test_store_evaluation_parameter(data_asset):
    data_asset.set_evaluation_parameter("my_parameter", "value")
    assert data_asset.get_evaluation_parameter("my_parameter") == "value"

    data_asset.set_evaluation_parameter(
        "my_second_parameter", [1, 2, "value", None, np.nan]
    )
    assert data_asset.get_evaluation_parameter("my_second_parameter") == [
        1,
        2,
        "value",
        None,
        np.nan,
    ]

    with pytest.raises(TypeError):
        data_asset.set_evaluation_parameter(
            ["a", "list", "cannot", "be", "a", "parameter"], "value"
        )


def test_store_evaluation_parameter_with_validator(validator_with_titanic_1911_asset):
    validator_with_titanic_1911_asset.set_evaluation_parameter("my_parameter", "value")
    assert (
        validator_with_titanic_1911_asset.get_evaluation_parameter("my_parameter")
        == "value"
    )

    validator_with_titanic_1911_asset.set_evaluation_parameter(
        "my_second_parameter",
        [1, 2, "value", None, np.nan, datetime.datetime(year=2022, month=12, day=15)],
    )
    assert validator_with_titanic_1911_asset.get_evaluation_parameter(
        "my_second_parameter"
    ) == [
        1,
        2,
        "value",
        None,
        None,
        "2022-12-15T00:00:00",
    ]

    with pytest.raises(TypeError):
        validator_with_titanic_1911_asset.set_evaluation_parameter(
            ["a", "list", "cannot", "be", "a", "parameter"], "value"
        )


def test_parameter_substitution(single_expectation_custom_data_asset):
    # Set our evaluation parameter from upstream
    single_expectation_custom_data_asset.set_evaluation_parameter(
        "upstream_dag_key", "upstream_dag_value"
    )

    # Establish our expectation using that parameter
    result = single_expectation_custom_data_asset.expect_nothing(
        expectation_argument={"$PARAMETER": "upstream_dag_key"}
    )
    suite = single_expectation_custom_data_asset.get_expectation_suite()

    # Ensure our value has been substituted during evaluation, and set properly in the suite
    assert result.result["details"]["expectation_argument"] == "upstream_dag_value"
    assert suite.evaluation_parameters == {"upstream_dag_key": "upstream_dag_value"}
    assert suite.expectations[0].kwargs == {
        "expectation_argument": {"$PARAMETER": "upstream_dag_key"}
    }


def test_parameter_substitution_with_validator(validator_with_titanic_1911_asset):
    # Set interactive_evaluation to False
    # validator_with_titanic_1911_asset.interactive_evaluation = False

    # Set our evaluation parameter from upstream
    validator_with_titanic_1911_asset.set_evaluation_parameter(
        "upstream_dag_key", "upstream_dag_value"
    )

    # Establish our expectation using that parameter
    result = validator_with_titanic_1911_asset.expect_nothing(
        expectation_argument={"$PARAMETER": "upstream_dag_key"}
    )
    suite = validator_with_titanic_1911_asset.get_expectation_suite()

    # Ensure our value has been substituted during evaluation, and set properly in the suite
    assert result.result["details"]["expectation_argument"] == "upstream_dag_value"
    assert suite.evaluation_parameters == {"upstream_dag_key": "upstream_dag_value"}
    assert suite.expectations[0].kwargs == {
        "expectation_argument": {"$PARAMETER": "upstream_dag_key"}
    }


def test_exploratory_parameter_substitution(single_expectation_custom_data_asset):
    # Establish our expectation using a parameter provided at runtime

    result = single_expectation_custom_data_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    suite = single_expectation_custom_data_asset.get_expectation_suite()
    # Ensure our value has been substituted during evaluation, and NOT stored in the suite
    assert result.result["details"]["expectation_argument"] == "temporary_value"
    assert suite.evaluation_parameters == {}
    assert suite.expectations[0].kwargs == {
        "expectation_argument": {"$PARAMETER": "upstream_dag_key"}
    }

    # Evaluating the expectation without the parameter should now fail, because no parameters were set
    with pytest.raises(EvaluationParameterError) as excinfo:
        single_expectation_custom_data_asset.validate(catch_exceptions=False)
    assert str(excinfo.value) == "No value found for $PARAMETER upstream_dag_key"

    # Setting a parameter value should allow it to succeed
    single_expectation_custom_data_asset.set_evaluation_parameter(
        "upstream_dag_key", "upstream_dag_value"
    )
    validation_result = single_expectation_custom_data_asset.validate()
    assert (
        validation_result.results[0].result["details"]["expectation_argument"]
        == "upstream_dag_value"
    )


def test_exploratory_parameter_substitution_with_validator(
    validator_with_titanic_1911_asset,
):
    # Establish our expectation using a parameter provided at runtime

    result = validator_with_titanic_1911_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    suite = validator_with_titanic_1911_asset.get_expectation_suite()
    # Ensure our value has been substituted during evaluation, and NOT stored in the suite
    assert result.result["details"]["expectation_argument"] == "temporary_value"
    assert suite.evaluation_parameters == {}
    assert suite.expectations[0].kwargs == {
        "expectation_argument": {"$PARAMETER": "upstream_dag_key"}
    }

    # Evaluating the expectation without the parameter should now fail, because no parameters were set
    with pytest.raises(EvaluationParameterError) as excinfo:
        validator_with_titanic_1911_asset.validate(catch_exceptions=False)
    assert str(excinfo.value) == "No value found for $PARAMETER upstream_dag_key"

    # Setting a parameter value should allow it to succeed
    validator_with_titanic_1911_asset.set_evaluation_parameter(
        "upstream_dag_key", "upstream_dag_value"
    )
    validation_result = validator_with_titanic_1911_asset.validate()
    assert (
        validation_result.results[0].result["details"]["expectation_argument"]
        == "upstream_dag_value"
    )


def test_validation_substitution(single_expectation_custom_data_asset):
    # Set up an expectation using a parameter, providing a default value.
    result = single_expectation_custom_data_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    assert result.result["details"]["expectation_argument"] == "temporary_value"

    # Provide a run-time evaluation parameter
    validation_result = single_expectation_custom_data_asset.validate(
        evaluation_parameters={"upstream_dag_key": "upstream_dag_value"}
    )
    assert (
        validation_result.results[0].result["details"]["expectation_argument"]
        == "upstream_dag_value"
    )


def test_validation_substitution_with_validator(validator_with_titanic_1911_asset):
    # Set up an expectation using a parameter, providing a default value.
    result = validator_with_titanic_1911_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    assert result.result["details"]["expectation_argument"] == "temporary_value"

    # Provide a run-time evaluation parameter
    validation_result = validator_with_titanic_1911_asset.validate(
        evaluation_parameters={"upstream_dag_key": "upstream_dag_value"}
    )
    assert (
        validation_result.results[0].result["details"]["expectation_argument"]
        == "upstream_dag_value"
    )


def test_validation_substitution_with_json_coercion(
    single_expectation_custom_data_asset,
):
    # Set up an expectation using a parameter, providing a default value.

    # Use a value that is a set. Note that there is no problem converting the type for the expectation (set -> list)
    result = single_expectation_custom_data_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": {"temporary_value"},
        }
    )
    assert result.result["details"]["expectation_argument"] == ["temporary_value"]

    # Provide a run-time evaluation parameter
    validation_result = single_expectation_custom_data_asset.validate(
        evaluation_parameters={"upstream_dag_key": {"upstream_dag_value"}}
    )
    assert validation_result.results[0].result["details"]["expectation_argument"] == [
        "upstream_dag_value"
    ]

    # Verify that the entire result object including evaluation_parameters is serializable
    assert validation_result["evaluation_parameters"]["upstream_dag_key"] == [
        "upstream_dag_value"
    ]
    try:
        json.dumps(expectationSuiteValidationResultSchema.dumps(validation_result))
    except TypeError as err:
        pytest.fail(
            "Error converting validation_result to json. Got TypeError: %s" + str(err)
        )


def test_validation_substitution_with_json_coercion_with_validator(
    validator_with_titanic_1911_asset,
):
    # Set up an expectation using a parameter, providing a default value.

    # Use a value that is a set. Note that there is no problem converting the type for the expectation (set -> list)
    result = validator_with_titanic_1911_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": {"temporary_value"},
        }
    )
    assert result.result["details"]["expectation_argument"] == ["temporary_value"]

    # Provide a run-time evaluation parameter
    validation_result = validator_with_titanic_1911_asset.validate(
        evaluation_parameters={"upstream_dag_key": {"upstream_dag_value"}}
    )
    assert validation_result.results[0].result["details"]["expectation_argument"] == [
        "upstream_dag_value"
    ]

    # Verify that the entire result object including evaluation_parameters is serializable
    assert validation_result["evaluation_parameters"]["upstream_dag_key"] == [
        "upstream_dag_value"
    ]
    try:
        json.dumps(expectationSuiteValidationResultSchema.dumps(validation_result))
    except TypeError as err:
        pytest.fail(
            "Error converting validation_result to json. Got TypeError: %s" + str(err)
        )


def test_validation_parameters_returned(single_expectation_custom_data_asset):
    single_expectation_custom_data_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    validation_result = single_expectation_custom_data_asset.validate(
        evaluation_parameters={"upstream_dag_key": "upstream_dag_value"}
    )
    assert validation_result["evaluation_parameters"] == {
        "upstream_dag_key": "upstream_dag_value"
    }


def test_validation_parameters_returned_with_validator(
    validator_with_titanic_1911_asset,
):
    validator_with_titanic_1911_asset.expect_nothing(
        expectation_argument={
            "$PARAMETER": "upstream_dag_key",
            "$PARAMETER.upstream_dag_key": "temporary_value",
        }
    )
    validation_result = validator_with_titanic_1911_asset.validate(
        evaluation_parameters={"upstream_dag_key": "upstream_dag_value"}
    )
    assert validation_result["evaluation_parameters"] == {
        "upstream_dag_key": "upstream_dag_value"
    }
