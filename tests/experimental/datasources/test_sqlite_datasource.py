from __future__ import annotations

import pathlib
from contextlib import _GeneratorContextManager, contextmanager
from typing import Any, Callable, Generator

import pytest
from pydantic import ValidationError

from great_expectations.experimental.datasources import SqliteDatasource
from great_expectations.experimental.datasources.sqlite_datasource import SqliteDsn
from tests.experimental.datasources.conftest import sqlachemy_execution_engine_mock_cls


@pytest.fixture
def sqlite_datasource_name() -> str:
    return "sqlite_datasource"


@pytest.fixture
def sqlite_database_path() -> pathlib.Path:
    relative_path = pathlib.Path(
        "..",
        "..",
        "test_sets",
        "taxi_yellow_tripdata_samples",
        "sqlite",
        "yellow_tripdata.db",
    )
    return pathlib.Path(__file__).parent.joinpath(relative_path).resolve(strict=True)


@pytest.fixture
def sqlite_datasource(sqlite_database_path, sqlite_datasource_name) -> SqliteDatasource:
    connection_string = f"sqlite:///{sqlite_database_path}"
    datasource = SqliteDatasource(
        name=sqlite_datasource_name,
        connection_string=connection_string,  # type: ignore[arg-type]  # pydantic will coerce
    )
    return datasource


@pytest.mark.unit
def test_connection_string_starts_with_sqlite(
    sqlite_datasource, sqlite_database_path, sqlite_datasource_name
):
    # The actual file doesn't matter only it's existence since SqlAlchemy does a check
    # when it creates the database engine.
    assert sqlite_datasource.name == sqlite_datasource_name
    assert sqlite_datasource.connection_string == f"sqlite:///{sqlite_database_path}"


@pytest.mark.unit
def test_connection_string_that_does_not_start_with_sqlite():
    name = "sqlite_datasource"
    connection_string = "stuff+sqlite:///path/to/database/file.db"
    with pytest.raises(ValidationError) as e:
        SqliteDatasource(
            name=name,
            connection_string=connection_string,
        )
    assert str(e.value) == (
        "1 validation error for SqliteDatasource\n"
        "connection_string\n"
        "  URL scheme not permitted (type=value_error.url.scheme; "
        f"allowed_schemes={SqliteDsn.allowed_schemes})"
    )


@pytest.mark.unit
def test_non_select_query_asset(sqlite_datasource):
    with pytest.raises(ValueError):
        sqlite_datasource.add_query_asset(name="query_asset", query="* from table")


# Test double used to return canned responses for splitter queries.
@contextmanager
def _create_sqlite_source(
    splitter_query_response: list[tuple[str]],
) -> Generator[Any, Any, Any]:
    execution_eng_cls = sqlachemy_execution_engine_mock_cls(
        validate_batch_spec=lambda _: None,
        dialect="sqlite",
        splitter_query_response=splitter_query_response,
    )
    # These type ignores when dealing with the execution_engine_override are because
    # it is a generic. We don't care about the exact type since we swap it out with our
    # mock for the purpose of this test and then replace it with the original.
    original_override = SqliteDatasource.execution_engine_override  # type: ignore[misc]
    try:
        SqliteDatasource.execution_engine_override = execution_eng_cls  # type: ignore[misc]
        yield SqliteDatasource(
            name="sqlite_datasource",
            connection_string="sqlite://",  # type: ignore[arg-type]  # pydantic will coerce
        )
    finally:
        SqliteDatasource.execution_engine_override = original_override  # type: ignore[misc]


@pytest.fixture
def create_sqlite_source() -> Callable[
    [list[tuple[str]]], _GeneratorContextManager[Any]
]:
    return _create_sqlite_source


@pytest.mark.unit
@pytest.mark.parametrize(
    [
        "add_splitter_method_name",
        "splitter_kwargs",
        "splitter_query_responses",
        "sorter_args",
        "all_batches_cnt",
        "specified_batch_request",
        "specified_batch_cnt",
        "last_specified_batch_metadata",
    ],
    [
        pytest.param(
            "add_splitter_hashed_column",
            {"column_name": "passenger_count", "hash_digits": 3},
            [("abc",), ("bcd",), ("xyz",)],
            ["hash"],
            3,
            {"hash": "abc"},
            1,
            {"hash": "abc"},
            id="hash",
        ),
        pytest.param(
            "add_splitter_converted_datetime",
            {"column_name": "pickup_datetime", "date_format_string": "%Y-%m-%d"},
            [("2019-02-01",), ("2019-02-23",)],
            ["datetime"],
            2,
            {"datetime": "2019-02-23"},
            1,
            {"datetime": "2019-02-23"},
            id="converted_datetime",
        ),
    ],
)
def test_sqlite_specific_column_splitter(
    create_sqlite_source,
    add_splitter_method_name,
    splitter_kwargs,
    splitter_query_responses,
    sorter_args,
    all_batches_cnt,
    specified_batch_request,
    specified_batch_cnt,
    last_specified_batch_metadata,
):
    with create_sqlite_source(
        splitter_query_response=[response for response in splitter_query_responses],
    ) as source:
        asset = source.add_query_asset(name="query_asset", query="SELECT * from table")
        getattr(asset, add_splitter_method_name)(**splitter_kwargs)
        asset.add_sorters(sorter_args)
        # Test getting all batches
        all_batches = asset.get_batch_list_from_batch_request(
            asset.build_batch_request()
        )
        assert len(all_batches) == all_batches_cnt
        # Test getting specified batches
        specified_batches = asset.get_batch_list_from_batch_request(
            asset.build_batch_request(specified_batch_request)
        )
        assert len(specified_batches) == specified_batch_cnt
        assert specified_batches[-1].metadata == last_specified_batch_metadata
