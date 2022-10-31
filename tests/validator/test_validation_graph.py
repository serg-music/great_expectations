import sys
from typing import Any, Dict, Iterable, Optional, Set, Tuple, Union, cast
from unittest import mock

import pytest

import great_expectations.exceptions as ge_exceptions
from great_expectations.core.expectation_configuration import ExpectationConfiguration
from great_expectations.execution_engine import ExecutionEngine
from great_expectations.expectations.core import ExpectColumnValueZScoresToBeLessThan
from great_expectations.validator.exception_info import ExceptionInfo
from great_expectations.validator.metric_configuration import MetricConfiguration
from great_expectations.validator.validation_graph import (
    MAX_METRIC_COMPUTATION_RETRIES,
    ExpectationValidationGraph,
    MetricEdge,
    ValidationGraph,
)


@pytest.fixture
def metric_edge(
    table_head_metric_config: MetricConfiguration,
    column_histogram_metric_config: MetricConfiguration,
) -> MetricEdge:
    return MetricEdge(
        left=table_head_metric_config, right=column_histogram_metric_config
    )


@pytest.fixture
def validation_graph_with_single_edge(metric_edge: MetricEdge) -> ValidationGraph:
    class DummyExecutionEngine:
        pass

    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    return ValidationGraph(execution_engine=execution_engine, edges=[metric_edge])


@pytest.fixture
def expect_column_values_to_be_unique_expectation_config() -> ExpectationConfiguration:
    return ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_unique",
        meta={},
        kwargs={"column": "provider_id", "result_format": "BASIC"},
    )


@pytest.fixture
def expect_column_value_z_scores_to_be_less_than_expectation_config() -> ExpectationConfiguration:
    return ExpectationConfiguration(
        expectation_type="expect_column_value_z_scores_to_be_less_than",
        kwargs={
            "column": "a",
            "mostly": 0.9,
            "threshold": 4,
            "double_sided": True,
        },
    )


@pytest.fixture
def expect_column_values_to_be_unique_expectation_validation_graph(
    expect_column_values_to_be_unique_expectation_config: ExpectationConfiguration,
) -> ExpectationValidationGraph:
    class DummyExecutionEngine:
        pass

    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    return ExpectationValidationGraph(
        execution_engine=execution_engine,
        configuration=expect_column_values_to_be_unique_expectation_config,
    )


@pytest.fixture
def expect_column_value_z_scores_to_be_less_than_expectation_validation_graph():
    class PandasExecutionEngineStub:
        pass

    PandasExecutionEngineStub.__name__ = "PandasExecutionEngine"
    execution_engine = cast(ExecutionEngine, PandasExecutionEngineStub())

    expectation_configuration = ExpectationConfiguration(
        expectation_type="expect_column_value_z_scores_to_be_less_than",
        kwargs={
            "column": "a",
            "mostly": 0.9,
            "threshold": 4,
            "double_sided": True,
        },
    )
    graph = ValidationGraph(execution_engine=execution_engine)
    validation_dependencies: Dict[
        str, Union[dict, Dict[str, MetricConfiguration]]
    ] = ExpectColumnValueZScoresToBeLessThan().get_validation_dependencies(
        expectation_configuration, execution_engine
    )

    for metric_configuration in validation_dependencies["metrics"].values():
        graph.build_metric_dependency_graph(
            metric_configuration=metric_configuration,
            runtime_configuration=None,
        )

    return graph


@pytest.mark.unit
def test_ValidationGraph_init_no_input_edges() -> None:
    class DummyExecutionEngine:
        pass

    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    graph = ValidationGraph(execution_engine=execution_engine)

    assert graph.edges == []
    assert graph.edge_ids == set()


@pytest.mark.unit
def test_ValidationGraph_init_with_input_edges(
    metric_edge: MetricEdge,
) -> None:
    class DummyExecutionEngine:
        pass

    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    edges = [metric_edge]
    graph = ValidationGraph(execution_engine=execution_engine, edges=edges)

    assert graph.edges == edges
    assert graph.edge_ids == {e.id for e in edges}


@pytest.mark.unit
def test_ValidationGraph_add(metric_edge: MetricEdge) -> None:
    class DummyExecutionEngine:
        pass

    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    graph = ValidationGraph(execution_engine=execution_engine)

    assert graph.edges == []
    assert graph.edge_ids == set()

    graph.add(edge=metric_edge)

    assert graph.edges == [metric_edge]
    assert metric_edge.id in graph.edge_ids


@pytest.mark.unit
def test_ExpectationValidationGraph_update(
    expect_column_values_to_be_unique_expectation_validation_graph: ExpectationValidationGraph,
    validation_graph_with_single_edge: ValidationGraph,
) -> None:
    assert (
        len(expect_column_values_to_be_unique_expectation_validation_graph.graph.edges)
        == 0
    )

    expect_column_values_to_be_unique_expectation_validation_graph.update(
        validation_graph_with_single_edge
    )

    assert (
        len(expect_column_values_to_be_unique_expectation_validation_graph.graph.edges)
        == 1
    )


@pytest.mark.unit
def test_ExpectationValidationGraph_get_exception_info(
    expect_column_values_to_be_unique_expectation_validation_graph: ExpectationValidationGraph,
    validation_graph_with_single_edge: ValidationGraph,
    metric_edge: MetricEdge,
) -> None:
    left = metric_edge.left
    right = metric_edge.right

    left_exception = ExceptionInfo(
        exception_traceback="my first traceback",
        exception_message="my first message",
    )
    right_exception = ExceptionInfo(
        exception_traceback="my second traceback",
        exception_message="my second message",
        raised_exception=False,
    )

    metric_info = {
        left.id: {"exception_info": {left_exception}},
        right.id: {"exception_info": {right_exception}},
    }

    expect_column_values_to_be_unique_expectation_validation_graph.update(
        validation_graph_with_single_edge
    )
    exception_info = expect_column_values_to_be_unique_expectation_validation_graph.get_exception_info(
        metric_info=metric_info
    )

    assert left_exception in exception_info
    assert right_exception in exception_info


@pytest.mark.unit
def test_parse_validation_graph(
    expect_column_value_z_scores_to_be_less_than_expectation_validation_graph: ValidationGraph,
):
    available_metrics: Dict[Tuple[str, str, str], Any]

    # Parse input "ValidationGraph" object and confirm the numbers of ready and still needed metrics.
    available_metrics = {}
    (
        ready_metrics,
        needed_metrics,
    ) = expect_column_value_z_scores_to_be_less_than_expectation_validation_graph._parse(
        metrics=available_metrics
    )
    assert len(ready_metrics) == 2 and len(needed_metrics) == 9

    # Show that including "nonexistent" metric in dictionary of resolved metrics does not increase ready_metrics count.
    available_metrics = {("nonexistent", "nonexistent", "nonexistent"): "NONE"}
    (
        ready_metrics,
        needed_metrics,
    ) = expect_column_value_z_scores_to_be_less_than_expectation_validation_graph._parse(
        metrics=available_metrics
    )
    assert len(ready_metrics) == 2 and len(needed_metrics) == 9


@pytest.mark.unit
def test_populate_dependencies(
    expect_column_value_z_scores_to_be_less_than_expectation_validation_graph: ValidationGraph,
):
    assert (
        len(
            expect_column_value_z_scores_to_be_less_than_expectation_validation_graph.edges
        )
        == 33
    )


@pytest.mark.unit
def test_populate_dependencies_with_incorrect_metric_name():
    class PandasExecutionEngineStub:
        pass

    PandasExecutionEngineStub.__name__ = "PandasExecutionEngine"
    execution_engine = cast(ExecutionEngine, PandasExecutionEngineStub())

    graph = ValidationGraph(execution_engine=execution_engine)

    with pytest.raises(ge_exceptions.MetricProviderError) as e:
        graph.build_metric_dependency_graph(
            metric_configuration=MetricConfiguration(
                metric_name="column_values.not_a_metric",
                metric_domain_kwargs={},
            ),
        )

    assert (
        e.value.message
        == "No provider found for column_values.not_a_metric using PandasExecutionEngine"
    )


@pytest.mark.unit
def test_resolve_validation_graph_with_bad_config_catch_exceptions_true():
    failed_metric_configuration = MetricConfiguration(
        metric_name="column.max",
        metric_domain_kwargs={
            "column": "not_in_table",
        },
        metric_value_kwargs={
            "parse_strings_as_datetimes": False,
        },
        metric_dependencies=None,
    )

    class PandasExecutionEngineFake:
        # noinspection PyUnusedLocal
        @staticmethod
        def resolve_metrics(
            metrics_to_resolve: Iterable[MetricConfiguration],
            metrics: Optional[Dict[Tuple[str, str, str], MetricConfiguration]] = None,
            runtime_configuration: Optional[dict] = None,
        ) -> Dict[Tuple[str, str, str], Any]:
            """
            This stub method implementation insures that specified "MetricConfiguration", designed to fail, will cause
            appropriate exception to be raised, while its dependencies resolve to actual values ("my_value" is used here
            as placeholder).  This makes "ValidationGraph.resolve_validation_graph()" -- method under test -- evaluate
            every "MetricConfiguration" of parsed "ValidationGraph" successfully, except "failed" "MetricConfiguration".
            """
            metric_configuration: MetricConfiguration
            if failed_metric_configuration.id in [
                metric_configuration.id for metric_configuration in metrics_to_resolve
            ]:
                raise ge_exceptions.MetricResolutionError(
                    message='Error: The column "not_in_table" in BatchData does not exist.',
                    failed_metrics=[failed_metric_configuration],
                )

            return {
                metric_configuration.id: "my_value"
                for metric_configuration in metrics_to_resolve
            }

    PandasExecutionEngineFake.__name__ = "PandasExecutionEngine"
    execution_engine = cast(ExecutionEngine, PandasExecutionEngineFake())

    graph = ValidationGraph(execution_engine=execution_engine)

    runtime_configuration = {
        "catch_exceptions": True,
        "result_format": {"result_format": "BASIC"},
    }

    graph.build_metric_dependency_graph(
        metric_configuration=failed_metric_configuration,
        runtime_configuration=runtime_configuration,
    )

    metrics: Dict[Tuple[str, str, str], Any] = {}
    aborted_metrics_info: Dict[
        Tuple[str, str, str],
        Dict[str, Union[MetricConfiguration, Set[ExceptionInfo], int]],
    ] = graph.resolve_validation_graph(
        metrics=metrics,
        runtime_configuration=runtime_configuration,
    )

    assert len(aborted_metrics_info) == 1

    aborted_metric_info_item = list(aborted_metrics_info.values())[0]
    assert aborted_metric_info_item["num_failures"] == MAX_METRIC_COMPUTATION_RETRIES

    assert len(aborted_metric_info_item["exception_info"]) == 1

    exception_info = next(iter(aborted_metric_info_item["exception_info"]))
    assert (
        exception_info["exception_message"]
        == 'Error: The column "not_in_table" in BatchData does not exist.'
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "show_progress_bars, are_progress_bars_disabled, ",
    [
        pytest.param(
            None,
            False,
        ),
        pytest.param(
            False,
            True,
        ),
    ],
)
def test_progress_bar_config(
    show_progress_bars: bool,
    are_progress_bars_disabled: bool,
):
    """
    This test creates mocked environment for progress bar tests; it then executes the method under test that utilizes
    the progress bar, "ValidationGraph.resolve_validation_graph()", with composed arguments, and verifies result.
    """

    class DummyMetricConfiguration:
        pass

    class DummyExecutionEngine:
        pass

    metric_configuration = cast(MetricConfiguration, DummyMetricConfiguration)
    execution_engine = cast(ExecutionEngine, DummyExecutionEngine)

    # ValidationGraph is a complex object that requires len > 3 to not trigger tqdm
    with mock.patch(
        "great_expectations.validator.validation_graph.ValidationGraph._parse",
        return_value=(
            {},
            {},
        ),
    ), mock.patch(
        "great_expectations.validator.validation_graph.ValidationGraph.edges",
        new_callable=mock.PropertyMock,
        return_value=[
            MetricEdge(left=metric_configuration),
            MetricEdge(left=metric_configuration),
            MetricEdge(left=metric_configuration),
        ],
    ), mock.patch(
        "great_expectations.validator.validation_graph.tqdm",
    ) as mock_tqdm:
        call_args = {
            "metrics": {},
            "runtime_configuration": None,
        }
        if show_progress_bars is not None:
            call_args.update(
                {
                    "show_progress_bars": show_progress_bars,
                }
            )

        graph = ValidationGraph(execution_engine=execution_engine)
        graph.resolve_validation_graph(**call_args)
        assert mock_tqdm.called is True
        assert mock_tqdm.call_args[1]["disable"] is are_progress_bars_disabled


if __name__ == "__main__":
    argv: list = sys.argv[1:]

    if argv and ((len(argv) > 1) or (argv[0] not in ["unit", "integration"])):
        raise ValueError(
            f'Value of test type can be only "unit" or "integration" ({argv} was entered.)'
        )

    test_type: str = "integration" if argv and argv[0] == "integration" else "unit"
    pytest.main(
        [
            __file__,
            f"-m {test_type}",
            "--durations=5",
            "--cloud",
            "--spark",
            "--cov=great_expectations/validator",
            "--cov-report=term",
            "--cov-report=html",
            "-svv",
            "--log-level=DEBUG",
        ]
    )
