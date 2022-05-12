from typing import List
from unittest import mock

import pytest
from mock_alchemy.comparison import ExpressionMatcher

from great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter import (
    DatePart,
    SqlAlchemyDataSplitter,
)
from tests.execution_engine.split_and_sample.split_and_sample_test_cases import (
    MULTIPLE_DATE_PART_BATCH_IDENTIFIERS,
    MULTIPLE_DATE_PART_DATE_PARTS,
    SINGLE_DATE_PART_BATCH_IDENTIFIERS,
    SINGLE_DATE_PART_DATE_PARTS,
)

# Here we add SqlAlchemyDataSplitter specific test cases to the generic test cases:
SINGLE_DATE_PART_DATE_PARTS += [
    pytest.param(
        [SqlAlchemyDataSplitter.date_part.MONTH],
        id="month getting date parts from SqlAlchemyDataSplitter.date_part",
    )
]
MULTIPLE_DATE_PART_DATE_PARTS += [
    pytest.param(
        [SqlAlchemyDataSplitter.date_part.YEAR, SqlAlchemyDataSplitter.date_part.MONTH],
        id="year_month getting date parts from SqlAlchemyDataSplitter.date_part",
    )
]


@mock.patch(
    "great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter.SqlAlchemyDataSplitter.split_on_date_parts"
)
@pytest.mark.parametrize(
    "splitter_method_name,called_with_date_parts",
    [
        ("split_on_year", [DatePart.YEAR]),
        ("split_on_year_and_month", [DatePart.YEAR, DatePart.MONTH]),
        (
            "split_on_year_and_month_and_day",
            [DatePart.YEAR, DatePart.MONTH, DatePart.DAY],
        ),
    ],
)
def test_named_date_part_methods(
    mock_split_on_date_parts: mock.MagicMock,
    splitter_method_name: str,
    called_with_date_parts: List[DatePart],
):
    """Test that a partially pre-filled version of split_on_date_parts() was called with the appropriate params.
    For example, split_on_year.
    """
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    column_name: str = "column_name"
    batch_identifiers: dict = {column_name: {"year": 2018, "month": 10, "day": 31}}

    getattr(data_splitter, splitter_method_name)(
        column_name=column_name,
        batch_identifiers=batch_identifiers,
    )

    mock_split_on_date_parts.assert_called_with(
        column_name=column_name,
        batch_identifiers=batch_identifiers,
        date_parts=called_with_date_parts,
    )


@pytest.mark.parametrize(
    "batch_identifiers_for_column",
    SINGLE_DATE_PART_BATCH_IDENTIFIERS,
)
@pytest.mark.parametrize(
    "date_parts",
    SINGLE_DATE_PART_DATE_PARTS,
)
def test_split_on_date_parts_single_date_parts(
    batch_identifiers_for_column, date_parts, sa
):
    """What does this test and why?

    split_on_date_parts should still build the correct query when passed a single element list
     date_parts that is a string, DatePart enum objects, mixed case string.
     To match our interface it should accept a dateutil parseable string as the batch identifier
     or a datetime and also fail when parameters are invalid.
    """

    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    column_name: str = "column_name"

    result: sa.sql.elements.BooleanClauseList = data_splitter.split_on_date_parts(
        column_name=column_name,
        batch_identifiers={column_name: batch_identifiers_for_column},
        date_parts=date_parts,
    )

    # using mock-alchemy
    assert ExpressionMatcher(result) == ExpressionMatcher(
        sa.and_(
            sa.extract("month", sa.column(column_name)) == 10,
        )
    )

    # using values
    assert isinstance(result, sa.sql.elements.BinaryExpression)

    assert isinstance(result.comparator.type, sa.Boolean)
    assert isinstance(result.left, sa.sql.elements.Extract)
    assert result.left.field == "month"
    assert result.left.expr.name == column_name
    assert result.right.effective_value == 10


@pytest.mark.parametrize(
    "batch_identifiers_for_column",
    MULTIPLE_DATE_PART_BATCH_IDENTIFIERS,
)
@pytest.mark.parametrize(
    "date_parts",
    MULTIPLE_DATE_PART_DATE_PARTS,
)
def test_split_on_date_parts_multiple_date_parts(
    batch_identifiers_for_column, date_parts, sa
):
    """What does this test and why?

    split_on_date_parts should still build the correct query when passed
     date parts that are strings, DatePart enum objects, a mixture and mixed case.
     To match our interface it should accept a dateutil parseable string as the batch identifier
     or a datetime and also fail when parameters are invalid.
    """

    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    column_name: str = "column_name"

    result: sa.sql.elements.BooleanClauseList = data_splitter.split_on_date_parts(
        column_name=column_name,
        batch_identifiers={column_name: batch_identifiers_for_column},
        date_parts=date_parts,
    )

    # using mock-alchemy
    assert ExpressionMatcher(result) == ExpressionMatcher(
        sa.and_(
            sa.extract("year", sa.column(column_name)) == 2018,
            sa.extract("month", sa.column(column_name)) == 10,
        )
    )

    # using values
    assert isinstance(result, sa.sql.elements.BooleanClauseList)

    assert isinstance(result.clauses[0].comparator.type, sa.Boolean)
    assert isinstance(result.clauses[0].left, sa.sql.elements.Extract)
    assert result.clauses[0].left.field == "year"
    assert result.clauses[0].left.expr.name == column_name
    assert result.clauses[0].right.effective_value == 2018

    assert isinstance(result.clauses[1].comparator.type, sa.Boolean)
    assert isinstance(result.clauses[1].left, sa.sql.elements.Extract)
    assert result.clauses[1].left.field == "month"
    assert result.clauses[1].left.expr.name == column_name
    assert result.clauses[1].right.effective_value == 10


@mock.patch(
    "great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter.SqlAlchemyDataSplitter.get_data_for_batch_identifiers_for_split_on_date_parts"
)
@mock.patch("great_expectations.execution_engine.execution_engine.ExecutionEngine")
def test_get_data_for_batch_identifiers_year(
    mock_execution_engine: mock.MagicMock,
    mock_get_data_for_batch_identifiers_for_split_on_date_parts: mock.MagicMock,
):
    """test that get_data_for_batch_identifiers_for_split_on_date_parts() was called with the appropriate params."""
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    table_name: str = "table_name"
    column_name: str = "column_name"

    data_splitter.get_data_for_batch_identifiers_year(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
    )

    mock_get_data_for_batch_identifiers_for_split_on_date_parts.assert_called_with(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
        date_parts=[DatePart.YEAR],
    )


@mock.patch(
    "great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter.SqlAlchemyDataSplitter.get_data_for_batch_identifiers_for_split_on_date_parts"
)
@mock.patch("great_expectations.execution_engine.execution_engine.ExecutionEngine")
def test_get_data_for_batch_identifiers_year_and_month(
    mock_execution_engine: mock.MagicMock,
    mock_get_data_for_batch_identifiers_for_split_on_date_parts: mock.MagicMock,
):
    """test that get_data_for_batch_identifiers_for_split_on_date_parts() was called with the appropriate params."""
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    table_name: str = "table_name"
    column_name: str = "column_name"

    data_splitter.get_data_for_batch_identifiers_year_and_month(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
    )

    mock_get_data_for_batch_identifiers_for_split_on_date_parts.assert_called_with(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
        date_parts=[DatePart.YEAR, DatePart.MONTH],
    )


@mock.patch(
    "great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter.SqlAlchemyDataSplitter.get_data_for_batch_identifiers_for_split_on_date_parts"
)
@mock.patch("great_expectations.execution_engine.execution_engine.ExecutionEngine")
def test_get_data_for_batch_identifiers_year_and_month_and_day(
    mock_execution_engine: mock.MagicMock,
    mock_get_data_for_batch_identifiers_for_split_on_date_parts: mock.MagicMock,
):
    """test that get_data_for_batch_identifiers_for_split_on_date_parts() was called with the appropriate params."""
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    table_name: str = "table_name"
    column_name: str = "column_name"

    data_splitter.get_data_for_batch_identifiers_year_and_month_and_day(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
    )

    mock_get_data_for_batch_identifiers_for_split_on_date_parts.assert_called_with(
        execution_engine=mock_execution_engine,
        table_name=table_name,
        column_name=column_name,
        date_parts=[DatePart.YEAR, DatePart.MONTH, DatePart.DAY],
    )


@pytest.mark.parametrize(
    "date_parts",
    SINGLE_DATE_PART_DATE_PARTS,
)
def test_get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts_single_date_parts(
    date_parts, sa
):
    """What does this test and why?

    get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts should still build the correct
    query when passed a single element list of date_parts that is a string, DatePart enum object, or mixed case string.
    """

    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    table_name: str = "table_name"
    column_name: str = "column_name"

    result: sa.sql.elements.BooleanClauseList = data_splitter.get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts(
        table_name=table_name,
        column_name=column_name,
        date_parts=date_parts,
    )

    assert isinstance(result, sa.sql.Select)

    query_str: str = (
        str(result.compile(compile_kwargs={"literal_binds": True}))
        .replace("\n", "")
        .replace(" ", "")
        .lower()
    )
    assert (
        query_str
        == (
            "SELECT distinct(EXTRACT(month FROM column_name)) AS concat_distinct_values, "
            "CAST(EXTRACT(month FROM column_name) AS INTEGER) AS month FROM table_name"
        )
        .replace("\n", "")
        .replace(" ", "")
        .lower()
    )


@pytest.mark.parametrize(
    "date_parts",
    MULTIPLE_DATE_PART_DATE_PARTS,
)
def test_get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts_multiple_date_parts(
    date_parts, sa
):
    """What does this test and why?
    get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts should
    return the correct query when passed any valid set of parameters including multiple date parts.
    """
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()
    table_name: str = "table_name"
    column_name: str = "column_name"

    result: sa.sql.elements.BooleanClauseList = data_splitter.get_split_query_for_data_for_batch_identifiers_for_split_on_date_parts(
        table_name=table_name,
        column_name=column_name,
        date_parts=date_parts,
    )

    assert isinstance(result, sa.sql.Select)

    query_str: str = (
        str(result.compile(compile_kwargs={"literal_binds": True}))
        .replace("\n", "")
        .replace(" ", "")
        .lower()
    )
    assert (
        query_str
        == (
            "SELECT distinct(concat(EXTRACT(year FROM column_name), EXTRACT(month FROM column_name))) AS concat_distinct_values,"
            "CAST(EXTRACT(year FROM column_name) AS INTEGER) AS year,"
            "CAST(EXTRACT(month FROM column_name) AS INTEGER) AS month"
            "FROM table_name"
        )
        .replace("\n", "")
        .replace(" ", "")
        .lower()
    )


@pytest.mark.parametrize(
    "underscore_prefix",
    [
        pytest.param("_", id="underscore prefix"),
        pytest.param("", id="no underscore prefix"),
    ],
)
@pytest.mark.parametrize(
    "splitter_method_name",
    [
        pytest.param(splitter_method_name, id=splitter_method_name)
        for splitter_method_name in [
            "split_on_year",
            "split_on_year_and_month",
            "split_on_year_and_month_and_day",
            "split_on_date_parts",
            "split_on_whole_table",
            "split_on_column_value",
            "split_on_converted_datetime",
            "split_on_divided_integer",
            "split_on_mod_integer",
            "split_on_multi_column_values",
            "split_on_hashed_column",
        ]
    ],
)
def test_get_splitter_method(underscore_prefix: str, splitter_method_name: str):
    data_splitter: SqlAlchemyDataSplitter = SqlAlchemyDataSplitter()

    splitter_method_name_with_prefix = f"{underscore_prefix}{splitter_method_name}"

    assert data_splitter.get_splitter_method(
        splitter_method_name_with_prefix
    ) == getattr(data_splitter, splitter_method_name)
