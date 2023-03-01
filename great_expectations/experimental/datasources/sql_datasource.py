from __future__ import annotations

import copy
import dataclasses
from pprint import pformat as pf
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
    cast,
)

import pydantic
from typing_extensions import Literal, Protocol, Self

import great_expectations.exceptions as gx_exceptions
from great_expectations.core.batch_spec import SqlAlchemyDatasourceBatchSpec
from great_expectations.execution_engine import SqlAlchemyExecutionEngine
from great_expectations.execution_engine.split_and_sample.data_splitter import DatePart
from great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter import (
    SqlAlchemyDataSplitter,
)
from great_expectations.experimental.datasources.experimental_base_model import (
    ExperimentalBaseModel,
)
from great_expectations.experimental.datasources.interfaces import (
    Batch,
    BatchRequest,
    BatchRequestOptions,
    BatchSorter,
    BatchSortersDefinition,
    DataAsset,
    Datasource,
    TestConnectionError,
)

SQLALCHEMY_IMPORTED = False
try:
    import sqlalchemy

    SQLALCHEMY_IMPORTED = True
except ImportError:
    pass


class SQLDatasourceError(Exception):
    pass


class _ColumnSplitter(Protocol):
    @property
    def columns(self) -> list[str]:
        """The names of the column used to split the data"""

    @property
    def method_name(self) -> str:
        """Returns a splitter method name.

        The possible values of splitter method names are defined in the enum,
        great_expectations.execution_engine.split_and_sample.data_splitter.SplitterMethod
        """

    @property
    def param_names(self) -> List[str]:
        """Returns the parameter names that specify a batch derived from this column splitter

        For example, for ColumnSplitterYearMonth this returns ["year", "month"]. For more
        examples, please see ColumnSplitter* classes below.
        """

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        """A shim to our sqlalchemy execution engine splitter methods

        We translate any internal _ColumnSplitter state and what is passed in from
        a batch_request to the splitter_kwargs required by our execution engine
        data splitters defined in:
        great_expectations.execution_engine.split_and_sample.sqlalchemy_data_splitter

        Look at ColumnSplitter* classes for concrete examples.
        """

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        """Translates `options` to the execution engine batch spec kwarg identifiers

        Arguments:
            options: A BatchRequest.options dictionary that specifies ALL the fields necessary
                     to specify a batch with respect to this column splitter.

        Returns:
            A dictionary that can be added to batch_spec_kwargs["batch_identifiers"].
            This has one of 2 forms:
              1. This category has many parameters are derived from 1 column.
                 The only are datetime column splitters and the batch_spec_kwargs["batch_identifiers"]
                 look like:
                   {column_name: {datepart_1: value, datepart_2: value, ...}
                 where datepart_* are strings like "year", "month", "day". The exact
                 fields depend on the splitter.

              2. This category has only 1 parameter for each column.
                 This is used for all other splitters and the batch_spec_kwargs["batch_identifiers"]
                 look like:
                   {column_name_1: value, column_name_2: value, ...}
                 where value is the value of the column after being processed by the splitter.
                 For example, for the ColumnSplitterModInteger where mod = 3,
                 {"passenger_count": 2}, means the raw passenger count value is in the set:
                 {2, 5, 8, ...} = {2*n + 1 | n is a nonnegative integer }
                 This category was only 1 parameter per column.
        """

    def param_defaults(self, sql_asset: _SQLAsset) -> List[Dict]:
        """Creates all valid batch requests options for sql_asset

        This can be implemented by querying the data defined in the sql_asset to generate
        all the possible parameter values for the BatchRequest.options that will return data.
        For example for a YearMonth splitter, we can query the underlying data to return the
        set of distinct (year, month) pairs. We would then return a list of BatchRequest.options,
        ie dictionaries, of the form {"year": year, "month": month} that contain all these distinct
        pairs.
        """


def _splitter_and_sql_asset_to_batch_identifier_data(
    splitter: _ColumnSplitter, asset: _SQLAsset
) -> list[dict]:
    execution_engine = asset.datasource.get_execution_engine()
    sqlalchemy_data_splitter = SqlAlchemyDataSplitter(execution_engine.dialect_name)
    return sqlalchemy_data_splitter.get_data_for_batch_identifiers(
        execution_engine=execution_engine,
        selectable=asset.as_selectable(),
        splitter_method_name=splitter.method_name,
        splitter_kwargs=splitter.splitter_method_kwargs(),
    )


class _ColumnSplitterDatetime(ExperimentalBaseModel):
    column_name: str
    method_name: str

    @property
    def columns(self) -> list[str]:
        return [self.column_name]

    def param_defaults(self, sql_asset: _SQLAsset) -> list[dict]:
        batch_identifier_data = _splitter_and_sql_asset_to_batch_identifier_data(
            splitter=self, asset=sql_asset
        )
        params: list[dict] = []
        for identifer_data in batch_identifier_data:
            params.append(identifer_data[self.column_name])
        return params

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        """Validates all the datetime parameters for this splitter exist in `options`."""
        identifiers: Dict = {}
        for part in self.param_names:
            if part not in options:
                raise ValueError(
                    f"'{part}' must be specified in the batch request options"
                )
            identifiers[part] = options[part]
        return {self.column_name: identifiers}

    @property
    def param_names(self) -> list[str]:
        raise NotImplementedError

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        raise NotImplementedError


class ColumnSplitterYear(_ColumnSplitterDatetime):
    column_name: str
    method_name: Literal["split_on_year"] = "split_on_year"

    @property
    def param_names(self) -> List[str]:
        return ["year"]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name}


class ColumnSplitterYearAndMonth(_ColumnSplitterDatetime):
    column_name: str
    method_name: Literal["split_on_year_and_month"] = "split_on_year_and_month"

    @property
    def param_names(self) -> List[str]:
        return ["year", "month"]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name}


class ColumnSplitterYearAndMonthAndDay(_ColumnSplitterDatetime):
    column_name: str
    method_name: Literal[
        "split_on_year_and_month_and_day"
    ] = "split_on_year_and_month_and_day"

    @property
    def param_names(self) -> List[str]:
        return ["year", "month", "day"]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name}


class ColumnSplitterDatetimePart(_ColumnSplitterDatetime):
    datetime_parts: List[str]
    column_name: str
    method_name: Literal["split_on_date_parts"] = "split_on_date_parts"

    @property
    def param_names(self) -> List[str]:
        return self.datetime_parts

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name, "date_parts": self.param_names}

    @pydantic.validator("datetime_parts", each_item=True)
    def _check_param_name_allowed(cls, v: str):
        allowed_date_parts = [part.value for part in DatePart]
        assert (
            v in allowed_date_parts
        ), f"Only the following param_names are allowed: {allowed_date_parts}"
        return v


class _ColumnSplitterOneColumnOneParam(ExperimentalBaseModel):
    column_name: str
    method_name: str

    @property
    def columns(self) -> list[str]:
        return [self.column_name]

    def param_defaults(self, sql_asset: _SQLAsset) -> list[dict]:
        batch_identifier_data = _splitter_and_sql_asset_to_batch_identifier_data(
            splitter=self, asset=sql_asset
        )
        params: list[dict] = []
        for identifer_data in batch_identifier_data:
            params.append({self.param_names[0]: identifer_data[self.column_name]})
        return params

    @property
    def param_names(self) -> list[str]:
        raise NotImplementedError

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        raise NotImplementedError

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ColumnSplitterDividedInteger(_ColumnSplitterOneColumnOneParam):
    divisor: int
    column_name: str
    method_name: Literal["split_on_divided_integer"] = "split_on_divided_integer"

    @property
    def param_names(self) -> List[str]:
        return ["quotient"]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name, "divisor": self.divisor}

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        if "quotient" not in options:
            raise ValueError(
                "'quotient' must be specified in the batch request options"
            )
        return {self.column_name: options["quotient"]}


class ColumnSplitterModInteger(_ColumnSplitterOneColumnOneParam):
    mod: int
    column_name: str
    method_name: Literal["split_on_mod_integer"] = "split_on_mod_integer"

    @property
    def param_names(self) -> List[str]:
        return ["remainder"]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name, "mod": self.mod}

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        if "remainder" not in options:
            raise ValueError(
                "'remainder' must be specified in the batch request options"
            )
        return {self.column_name: options["remainder"]}


class ColumnSplitterColumnValue(_ColumnSplitterOneColumnOneParam):
    column_name: str
    method_name: Literal["split_on_column_value"] = "split_on_column_value"

    @property
    def param_names(self) -> List[str]:
        return [self.column_name]

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_name": self.column_name}

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        if self.column_name not in options:
            raise ValueError(
                f"'{self.column_name}' must be specified in the batch request options"
            )
        return {self.column_name: options[self.column_name]}

    def param_defaults(self, sql_asset: _SQLAsset) -> list[dict]:
        # The superclass version of param_defaults is correct, but here we leverage that
        # the parameter name is the same as the column name to make this much faster.
        return _splitter_and_sql_asset_to_batch_identifier_data(
            splitter=self, asset=sql_asset
        )


class ColumnSplitterMultiColumnValue(ExperimentalBaseModel):
    column_names: List[str]
    method_name: Literal[
        "split_on_multi_column_values"
    ] = "split_on_multi_column_values"

    @property
    def columns(self):
        return self.column_names

    @property
    def param_names(self) -> List[str]:
        return self.column_names

    def splitter_method_kwargs(self) -> Dict[str, Any]:
        return {"column_names": self.column_names}

    def batch_request_options_to_batch_spec_kwarg_identifiers(
        self, options: BatchRequestOptions
    ) -> Dict[str, Any]:
        if not (set(self.column_names) <= set(options.keys())):
            raise ValueError(
                f"All column names, {self.column_names}, must be specified in the batch request options. "
                f" The options provided were f{options}."
            )
        return {col: options[col] for col in self.column_names}

    def param_defaults(self, sql_asset: _SQLAsset) -> list[dict]:
        return _splitter_and_sql_asset_to_batch_identifier_data(
            splitter=self, asset=sql_asset
        )


# We create this type instead of using _ColumnSplitter so pydantic can use to this to
# coerce the column splitter to the right type during deserialization from config.
ColumnSplitter = Union[
    ColumnSplitterColumnValue,
    ColumnSplitterMultiColumnValue,
    ColumnSplitterDividedInteger,
    ColumnSplitterModInteger,
    ColumnSplitterYear,
    ColumnSplitterYearAndMonth,
    ColumnSplitterYearAndMonthAndDay,
    ColumnSplitterDatetimePart,
]


class _SQLAsset(DataAsset):
    # Instance fields
    type: str = pydantic.Field("_sql_asset")
    column_splitter: Optional[ColumnSplitter] = None
    name: str

    def batch_request_options_template(
        self,
    ) -> BatchRequestOptions:
        """A BatchRequestOptions template for build_batch_request.

        Returns:
            A BatchRequestOptions dictionary with the correct shape that build_batch_request
            will understand. All the option values are defaulted to None.
        """
        template: BatchRequestOptions = {}
        if not self.column_splitter:
            return template
        return {p: None for p in self.column_splitter.param_names}

    def _add_splitter(self: Self, column_splitter: ColumnSplitter) -> Self:
        self.column_splitter = column_splitter
        self.test_column_splitter_connection()
        return self

    def add_splitter_year(
        self: Self,
        column_name: str,
    ) -> Self:
        """Associates a year splitter with this sql data asset.
        Args:
            column_name: A column name of the date column where year and month will be parsed out.
        Returns:
            This sql asset so we can use this method fluently.
        """
        return self._add_splitter(
            ColumnSplitterYear(method_name="split_on_year", column_name=column_name)
        )

    def add_splitter_year_and_month(
        self: Self,
        column_name: str,
    ) -> Self:
        """Associates a year, month splitter with this sql asset.
        Args:
            column_name: A column name of the date column where year and month will be parsed out.
        Returns:
            This sql asset so we can use this method fluently.
        """
        return self._add_splitter(
            ColumnSplitterYearAndMonth(
                method_name="split_on_year_and_month", column_name=column_name
            )
        )

    def add_splitter_year_and_month_and_day(
        self: Self,
        column_name: str,
    ) -> Self:
        """Associates a year, month, day splitter with this sql asset.
        Args:
            column_name: A column name of the date column where year and month will be parsed out.
        Returns:
            This sql asset so we can use this method fluently.
        """
        return self._add_splitter(
            ColumnSplitterYearAndMonthAndDay(
                method_name="split_on_year_and_month_and_day", column_name=column_name
            )
        )

    def add_splitter_datetime_part(
        self: Self, column_name: str, datetime_parts: List[str]
    ) -> Self:
        return self._add_splitter(
            ColumnSplitterDatetimePart(
                method_name="split_on_date_parts",
                column_name=column_name,
                datetime_parts=datetime_parts,
            )
        )

    def add_splitter_column_value(self: Self, column_name: str) -> Self:
        return self._add_splitter(
            ColumnSplitterColumnValue(
                method_name="split_on_column_value",
                column_name=column_name,
            )
        )

    def add_splitter_divided_integer(
        self: Self, column_name: str, divisor: int
    ) -> Self:
        return self._add_splitter(
            ColumnSplitterDividedInteger(
                method_name="split_on_divided_integer",
                column_name=column_name,
                divisor=divisor,
            )
        )

    def add_splitter_mod_integer(self: Self, column_name: str, mod: int) -> Self:
        return self._add_splitter(
            ColumnSplitterModInteger(
                method_name="split_on_mod_integer",
                column_name=column_name,
                mod=mod,
            )
        )

    def add_splitter_multi_column_values(self: Self, column_names: list[str]) -> Self:
        return self._add_splitter(
            ColumnSplitterMultiColumnValue(
                column_names=column_names, method_name="split_on_multi_column_values"
            )
        )

    def test_connection(self) -> None:
        pass

    def test_column_splitter_connection(self) -> None:
        pass

    @staticmethod
    def _matches_request_options(
        candidate: Dict, requested_options: BatchRequestOptions
    ) -> bool:
        for k, v in requested_options.items():
            if v is not None and candidate[k] != v:
                return False
        return True

    def _fully_specified_batch_requests(
        self, batch_request: BatchRequest
    ) -> List[BatchRequest]:
        """Populates a batch requests unspecified params producing a list of batch requests."""
        if self.column_splitter is None:
            # Currently batch_request.options is complete determined by the presence of a
            # column splitter. If column_splitter is None, then there are no specifiable options
            # so we return early. Since the passed in batch_request is verified, it must be the
            # empty, ie {}.
            # In the future, if there are options that are not determined by the column splitter
            # this check will have to be generalized.
            return [batch_request]

        batch_requests: List[BatchRequest] = []
        # We iterate through all possible batches as determined by the column splitter
        for params in self.column_splitter.param_defaults(self):
            # If the params from the column splitter don't match the batch request options
            # we don't create this batch.
            if not _SQLAsset._matches_request_options(params, batch_request.options):
                continue
            options = copy.deepcopy(batch_request.options)
            options.update(params)
            batch_requests.append(
                BatchRequest(
                    datasource_name=batch_request.datasource_name,
                    data_asset_name=batch_request.data_asset_name,
                    options=options,
                )
            )
        return batch_requests

    def get_batch_list_from_batch_request(
        self, batch_request: BatchRequest
    ) -> List[Batch]:
        """A list of batches that match the BatchRequest.

        Args:
            batch_request: A batch request for this asset. Usually obtained by calling
                build_batch_request on the asset.

        Returns:
            A list of batches that match the options specified in the batch request.
        """
        self._validate_batch_request(batch_request)

        batch_list: List[Batch] = []
        column_splitter = self.column_splitter
        batch_spec_kwargs: dict[str, str | dict | None]
        for request in self._fully_specified_batch_requests(batch_request):
            batch_metadata = copy.deepcopy(request.options)
            batch_spec_kwargs = self._create_batch_spec_kwargs()
            if column_splitter:
                batch_spec_kwargs["splitter_method"] = column_splitter.method_name
                batch_spec_kwargs[
                    "splitter_kwargs"
                ] = column_splitter.splitter_method_kwargs()
                # mypy infers that batch_spec_kwargs["batch_identifiers"] is a collection, but
                # it is hardcoded to a dict above, so we cast it here.
                cast(Dict, batch_spec_kwargs["batch_identifiers"]).update(
                    column_splitter.batch_request_options_to_batch_spec_kwarg_identifiers(
                        request.options
                    )
                )
            # Creating the batch_spec is our hook into the execution engine.
            batch_spec = SqlAlchemyDatasourceBatchSpec(**batch_spec_kwargs)
            execution_engine: SqlAlchemyExecutionEngine = (
                self.datasource.get_execution_engine()
            )
            data, markers = execution_engine.get_batch_data_and_markers(
                batch_spec=batch_spec
            )

            # batch_definition (along with batch_spec and markers) is only here to satisfy a
            # legacy constraint when computing usage statistics in a validator. We hope to remove
            # it in the future.
            # imports are done inline to prevent a circular dependency with core/batch.py
            from great_expectations.core import IDDict
            from great_expectations.core.batch import BatchDefinition

            batch_definition = BatchDefinition(
                datasource_name=self.datasource.name,
                data_connector_name="fluent_sql",
                data_asset_name=self.name,
                batch_identifiers=IDDict(batch_spec["batch_identifiers"]),
                batch_spec_passthrough=None,
            )

            # Some pydantic annotations are postponed due to circular imports.
            # Batch.update_forward_refs() will set the annotations before we
            # instantiate the Batch class since we can import them in this scope.
            Batch.update_forward_refs()
            batch_list.append(
                Batch(
                    datasource=self.datasource,
                    data_asset=self,
                    batch_request=request,
                    data=data,
                    metadata=batch_metadata,
                    legacy_batch_markers=markers,
                    legacy_batch_spec=batch_spec,
                    legacy_batch_definition=batch_definition,
                )
            )
        self.sort_batches(batch_list)
        return batch_list

    def build_batch_request(
        self, options: Optional[BatchRequestOptions] = None
    ) -> BatchRequest:
        """A batch request that can be used to obtain batches for this DataAsset.

        Args:
            options: A dict that can be used to limit the number of batches returned from the asset.
                The dict structure depends on the asset type. A template of the dict can be obtained by
                calling batch_request_options_template.

        Returns:
            A BatchRequest object that can be used to obtain a batch list from a Datasource by calling the
            get_batch_list_from_batch_request method.
        """
        if options is not None and not self._valid_batch_request_options(options):
            allowed_keys = set(self.batch_request_options_template().keys())
            actual_keys = set(options.keys())
            raise gx_exceptions.InvalidBatchRequestError(
                "Batch request options should only contain keys from the following set:\n"
                f"{allowed_keys}\nbut your specified keys contain\n"
                f"{actual_keys.difference(allowed_keys)}\nwhich is not valid.\n"
            )
        return BatchRequest(
            datasource_name=self.datasource.name,
            data_asset_name=self.name,
            options=options or {},
        )

    def _validate_batch_request(self, batch_request: BatchRequest) -> None:
        """Validates the batch_request has the correct form.

        Args:
            batch_request: A batch request object to be validated.
        """
        if not (
            batch_request.datasource_name == self.datasource.name
            and batch_request.data_asset_name == self.name
            and self._valid_batch_request_options(batch_request.options)
        ):
            expect_batch_request_form = BatchRequest(
                datasource_name=self.datasource.name,
                data_asset_name=self.name,
                options=self.batch_request_options_template(),
            )
            raise gx_exceptions.InvalidBatchRequestError(
                "BatchRequest should have form:\n"
                f"{pf(dataclasses.asdict(expect_batch_request_form))}\n"
                f"but actually has form:\n{pf(dataclasses.asdict(batch_request))}\n"
            )

    def _create_batch_spec_kwargs(self) -> dict[str, Any]:
        """Creates batch_spec_kwargs used to instantiate a SqlAlchemyDatasourceBatchSpec

        This is called by get_batch_list_from_batch_request to generate the batches.

        Returns:
            A dictionary that will be passed to SqlAlchemyDatasourceBatchSpec(**returned_dict)
        """
        raise NotImplementedError

    def as_selectable(self) -> sqlalchemy.sql.Selectable:
        """Returns a Selectable that can be used to query this data

        Returns:
            A Selectable that can be used in a from clause to query this data
        """
        raise NotImplementedError


class QueryAsset(_SQLAsset):
    # Instance fields
    type: Literal["query"] = "query"
    query: str

    @pydantic.validator("query")
    def query_must_start_with_select(cls, v: str):
        query = v.lstrip()
        if not (query.upper().startswith("SELECT") and query[6].isspace()):
            raise ValueError("query must start with 'SELECT' followed by a whitespace.")
        return v

    def as_selectable(self) -> sqlalchemy.sql.Selectable:
        """Returns the Selectable that is used to retrieve the data.

        This can be used in a subselect FROM clause for queries against this data.
        """
        return sqlalchemy.select(sqlalchemy.text(self.query.lstrip()[6:])).subquery()

    def _create_batch_spec_kwargs(self) -> dict[str, Any]:
        return {
            "data_asset_name": self.name,
            "query": self.query,
            "temp_table_schema_name": None,
            "batch_identifiers": {},
        }


class TableAsset(_SQLAsset):
    """A _SQLAsset Mixin

    This is used as a mixin for _SQLAsset subclasses to give them the TableAsset functionality
    that can be used by different SQL datasource subclasses.

    For example see TableAsset defined in this module and SqliteTableAsset defined in
    sqlite_datasource.py
    """

    # Instance fields
    type: Literal["table"] = "table"
    table_name: str
    schema_name: Optional[str] = None

    @property
    def qualified_name(self) -> str:
        return (
            f"{self.schema_name}.{self.table_name}"
            if self.schema_name
            else self.table_name
        )

    def test_connection(self) -> None:
        """Test the connection for the TableAsset.

        Raises:
            TestConnectionError: If the connection test fails.
        """
        datasource: SQLDatasource = self.datasource
        engine: sqlalchemy.engine.Engine = datasource.get_engine()
        inspector: sqlalchemy.engine.Inspector = sqlalchemy.inspect(engine)

        if self.schema_name and self.schema_name not in inspector.get_schema_names():
            raise TestConnectionError(
                f'Attempt to connect to table: "{self.qualified_name}" failed because the schema '
                f'"{self.schema_name}" does not exist.'
            )

        table_exists = sqlalchemy.inspect(engine).has_table(
            table_name=self.table_name,
            schema=self.schema_name,
        )
        if not table_exists:
            raise TestConnectionError(
                f'Attempt to connect to table: "{self.qualified_name}" failed because the table '
                f'"{self.table_name}" does not exist.'
            )

    def test_column_splitter_connection(self) -> None:
        if self.column_splitter:
            datasource: SQLDatasource = self.datasource
            engine: sqlalchemy.engine.Engine = datasource.get_engine()
            inspector: sqlalchemy.engine.Inspector = sqlalchemy.inspect(engine)

            columns: list[dict[str, Any]] = inspector.get_columns(
                table_name=self.table_name, schema=self.schema_name
            )
            column_names: list[str] = [column["name"] for column in columns]
            for splitter_column_name in self.column_splitter.columns:
                if splitter_column_name not in column_names:
                    raise TestConnectionError(
                        f'The column "{splitter_column_name}" was not found in table "{self.qualified_name}"'
                    )

    def as_selectable(self) -> sqlalchemy.sql.Selectable:
        """Returns the table as a sqlalchemy Selectable.

        This can be used in a from clause for a query against this data.
        """
        import sqlalchemy as sa

        return sa.text(self.table_name)

    def _create_batch_spec_kwargs(self) -> dict[str, Any]:
        return {
            "type": "table",
            "data_asset_name": self.name,
            "table_name": self.table_name,
            "schema_name": self.schema_name,
            "batch_identifiers": {},
        }


class SQLDatasource(Datasource):
    """Adds a generic SQL datasource to the data context.

    Args:
        name: The name of this datasource.
        connection_string: The SQLAlchemy connection string used to connect to the database.
            For example: "postgresql+psycopg2://postgres:@localhost/test_database"
        assets: An optional dictionary whose keys are SQL DataAsset names and whose values
            are SQL DataAsset objects.
    """

    # class var definitions
    asset_types: ClassVar[List[Type[DataAsset]]] = [TableAsset, QueryAsset]

    # right side of the operator determines the type name
    # left side enforces the names on instance creation
    type: Literal["sql"] = "sql"
    connection_string: str
    # We need to explicitly add each asset type to the Union due to how
    # deserialization is implemented in our pydantic base model.
    assets: Dict[str, Union[TableAsset, QueryAsset]] = {}

    # private attrs
    _cached_connection_string: str = pydantic.PrivateAttr("")
    _engine: Union[sqlalchemy.engine.Engine, None] = pydantic.PrivateAttr(None)
    # These are instance var because ClassVars can't contain Type variables. See
    # https://peps.python.org/pep-0526/#class-and-instance-variable-annotations
    _TableAsset: Type[TableAsset] = pydantic.PrivateAttr(TableAsset)
    _QueryAsset: Type[QueryAsset] = pydantic.PrivateAttr(QueryAsset)

    @property
    def execution_engine_type(self) -> Type[SqlAlchemyExecutionEngine]:
        """Returns the default execution engine type."""
        return SqlAlchemyExecutionEngine

    def get_engine(self) -> sqlalchemy.engine.Engine:
        if self.connection_string != self._cached_connection_string or not self._engine:
            # validate that SQL Alchemy was successfully imported and attempt to create an engine
            if SQLALCHEMY_IMPORTED:
                try:
                    self._engine = sqlalchemy.create_engine(self.connection_string)
                except Exception as e:
                    # connection_string has passed pydantic validation, but still fails to create a sqlalchemy engine
                    # one possible case is a missing plugin (e.g. psycopg2)
                    raise SQLDatasourceError(
                        "Unable to create a SQLAlchemy engine from "
                        f"connection_string: {self.connection_string} due to the "
                        f"following exception: {str(e)}"
                    ) from e
                self._cached_connection_string = self.connection_string
            else:
                raise SQLDatasourceError(
                    "Unable to create SQLDatasource due to missing sqlalchemy dependency."
                )
        return self._engine

    def test_connection(self, test_assets: bool = True) -> None:
        """Test the connection for the SQLDatasource.

        Args:
            test_assets: If assets have been passed to the SQLDatasource, whether to test them as well.

        Raises:
            TestConnectionError: If the connection test fails.
        """
        try:
            engine: sqlalchemy.engine.Engine = self.get_engine()
            engine.connect()
        except Exception as e:
            raise TestConnectionError(
                "Attempt to connect to datasource failed with the following error message: "
                f"{str(e)}"
            ) from e
        if self.assets and test_assets:
            for asset in self.assets.values():
                asset._datasource = self
                asset.test_connection()

    def add_table_asset(
        self,
        name: str,
        table_name: str,
        schema_name: Optional[str] = None,
        order_by: Optional[BatchSortersDefinition] = None,
    ) -> TableAsset:
        """Adds a table asset to this datasource.

        Args:
            name: The name of this table asset.
            table_name: The table where the data resides.
            schema_name: The schema that holds the table.
            order_by: A list of BatchSorters or BatchSorter strings.

        Returns:
            The table asset that is added to the datasource.
            The type of this object will match the necessary type for this datasource.
            eg, it could be a TableAsset or a SqliteTableAsset.
        """
        order_by_sorters: list[BatchSorter] = self.parse_order_by_sorters(
            order_by=order_by
        )
        asset = self._TableAsset(
            name=name,
            table_name=table_name,
            schema_name=schema_name,
            order_by=order_by_sorters,
        )
        return self.add_asset(asset)

    def add_query_asset(
        self,
        name: str,
        query: str,
        order_by: Optional[BatchSortersDefinition] = None,
    ) -> QueryAsset:
        """Adds a query asset to this datasource.

        Args:
            name: The name of this table asset.
            query: The SELECT query to selects the data to validate. It must begin with the "SELECT".
            order_by: A list of BatchSorters or BatchSorter strings.

        Returns:
            The query asset that is added to the datasource.
            The type of this object will match the necessary type for this datasource.
            eg, it could be a QueryAsset or a SqliteQueryAsset.
        """
        order_by_sorters: list[BatchSorter] = self.parse_order_by_sorters(
            order_by=order_by
        )
        asset = self._QueryAsset(
            name=name,
            query=query,
            order_by=order_by_sorters,
        )
        return self.add_asset(asset)
