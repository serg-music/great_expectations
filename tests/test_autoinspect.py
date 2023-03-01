"""
Tests for autoinspection framework.
"""

import pytest

import great_expectations as gx
import great_expectations.core.expectation_configuration
from great_expectations.core.expectation_configuration import ExpectationConfiguration
from great_expectations.self_check.util import get_dataset


def test_no_autoinspection():
    df = gx.dataset.PandasDataset({"a": [1, 2, 3]}, profiler=None)
    suite = df.get_expectation_suite()

    assert len(suite.expectations) == 0


def test_default_no_autoinspection():
    df = gx.dataset.PandasDataset({"a": [1, 2, 3]})
    suite = df.get_expectation_suite()

    assert len(suite.expectations) == 0


def test_autoinspect_existing_dataset(test_backend):
    # Get a basic dataset with no expectations
    df = get_dataset(test_backend, {"a": [1, 2, 3]}, profiler=None)
    suite = df.get_expectation_suite()
    assert len(suite.expectations) == 0

    # Run autoinspect
    df.profile(gx.profile.ColumnsExistProfiler)
    suite = df.get_expectation_suite()

    # Ensure that autoinspect worked
    assert len(suite.expectations) == 1
    assert suite.expectations == [
        great_expectations.core.expectation_configuration.ExpectationConfiguration(
            expectation_type="expect_column_to_exist", kwargs={"column": "a"}
        )
    ]


def test_autoinspect_columns_exist(test_backend):
    df = get_dataset(
        test_backend, {"a": [1, 2, 3]}, profiler=gx.profile.ColumnsExistProfiler
    )
    suite = df.get_expectation_suite()

    assert len(suite.expectations) == 1
    assert suite.expectations == [
        ExpectationConfiguration(
            expectation_type="expect_column_to_exist", kwargs={"column": "a"}
        )
    ]


def test_autoinspect_warning():
    with pytest.raises(NotImplementedError):
        gx.dataset.Dataset(profiler=gx.profile.ColumnsExistProfiler)
