import logging
import os
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Union, cast

import requests

import great_expectations.exceptions as ge_exceptions
from great_expectations import __version__
from great_expectations.core import ExpectationSuite
from great_expectations.core.serializer import JsonConfigSerializer
from great_expectations.data_context.data_context.abstract_data_context import (
    AbstractDataContext,
)
from great_expectations.data_context.data_context_variables import (
    CloudDataContextVariables,
)
from great_expectations.data_context.store.ge_cloud_store_backend import (
    GeCloudRESTResource,
)
from great_expectations.data_context.types.base import (
    DEFAULT_USAGE_STATISTICS_URL,
    DataContextConfig,
    DataContextConfigDefaults,
    GeCloudConfig,
    datasourceConfigSchema,
)
from great_expectations.data_context.types.refs import GeCloudResourceRef
from great_expectations.data_context.types.resource_identifiers import GeCloudIdentifier
from great_expectations.data_context.util import substitute_all_config_variables
from great_expectations.exceptions.exceptions import DataContextError

if TYPE_CHECKING:
    from great_expectations.checkpoint.checkpoint import Checkpoint

logger = logging.getLogger(__name__)


class GECloudEnvironmentVariable(str, Enum):
    BASE_URL = "GE_CLOUD_BASE_URL"
    ORGANIZATION_ID = "GE_CLOUD_ORGANIZATION_ID"
    ACCESS_TOKEN = "GE_CLOUD_ACCESS_TOKEN"


class CloudDataContext(AbstractDataContext):
    """
    Subclass of AbstractDataContext that contains functionality necessary to hydrate state from cloud
    """

    def __init__(
        self,
        project_config: Optional[Union[DataContextConfig, Mapping]] = None,
        context_root_dir: Optional[str] = None,
        runtime_environment: Optional[dict] = None,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> None:
        """
        CloudDataContext constructor

        Args:
            project_config (DataContextConfig): config for CloudDataContext
            runtime_environment (dict):  a dictionary of config variables that override both those set in
                config_variables.yml and the environment
            ge_cloud_config (GeCloudConfig): GeCloudConfig corresponding to current CloudDataContext
        """
        self._ge_cloud_mode = True  # property needed for backward compatibility

        self._ge_cloud_config = self.get_ge_cloud_config(
            ge_cloud_base_url=ge_cloud_base_url,
            ge_cloud_access_token=ge_cloud_access_token,
            ge_cloud_organization_id=ge_cloud_organization_id,
        )

        self._context_root_directory = self.determine_context_root_directory(
            context_root_dir
        )

        if project_config is None:
            project_config = self.retrieve_data_context_config_from_ge_cloud(
                ge_cloud_config=self._ge_cloud_config,
            )
        self._project_config = self._apply_global_config_overrides(
            config=project_config
        )
        self._variables = self._init_variables()
        super().__init__(
            runtime_environment=runtime_environment,
        )

    @classmethod
    def is_ge_cloud_config_available(
        cls,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> bool:
        """
        Helper method called by gx.get_context() method to determine whether all the information needed
        to build a ge_cloud_config is available.

        If provided as explicit arguments, ge_cloud_base_url, ge_cloud_access_token and
        ge_cloud_organization_id will use runtime values instead of environment variables or conf files.

        If any of the values are missing, the method will return False. It will return True otherwise.

        Args:
            ge_cloud_base_url: Optional, you may provide this alternatively via
                environment variable GE_CLOUD_BASE_URL or within a config file.
            ge_cloud_access_token: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ACCESS_TOKEN or within a config file.
            ge_cloud_organization_id: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ORGANIZATION_ID or within a config file.

        Returns:
            bool: Is all the information needed to build a ge_cloud_config is available?
        """
        ge_cloud_config_dict = cls._get_ge_cloud_config_dict(
            ge_cloud_base_url=ge_cloud_base_url,
            ge_cloud_access_token=ge_cloud_access_token,
            ge_cloud_organization_id=ge_cloud_organization_id,
        )
        for key, val in ge_cloud_config_dict.items():
            if not val:
                return False
        return True

    @classmethod
    def determine_context_root_directory(cls, context_root_dir: Optional[str]) -> str:
        if context_root_dir is None:
            context_root_dir = os.getcwd()
            logger.info(
                f'context_root_dir was not provided - defaulting to current working directory "'
                f'{context_root_dir}".'
            )
        return os.path.abspath(os.path.expanduser(context_root_dir))

    @classmethod
    def retrieve_data_context_config_from_ge_cloud(
        cls, ge_cloud_config: GeCloudConfig
    ) -> DataContextConfig:
        """
        Utilizes the GeCloudConfig instantiated in the constructor to create a request to the Cloud API.
        Given proper authorization, the request retrieves a data context config that is pre-populated with
        GE objects specific to the user's Cloud environment (datasources, data connectors, etc).

        Please note that substitution for ${VAR} variables is performed in GE Cloud before being sent
        over the wire.

        :return: the configuration object retrieved from the Cloud API
        """
        base_url = ge_cloud_config.base_url  # type: ignore[union-attr]
        organization_id = ge_cloud_config.organization_id  # type: ignore[union-attr]
        ge_cloud_url = (
            f"{base_url}/organizations/{organization_id}/data-context-configuration"
        )
        headers = {
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {ge_cloud_config.access_token}",  # type: ignore[union-attr]
            "Gx-Version": __version__,
        }

        response = requests.get(ge_cloud_url, headers=headers)
        if response.status_code != 200:
            raise ge_exceptions.GeCloudError(
                f"Bad request made to GE Cloud; {response.text}"
            )
        config = response.json()
        return DataContextConfig(**config)

    @classmethod
    def get_ge_cloud_config(
        cls,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> GeCloudConfig:
        """
        Build a GeCloudConfig object. Config attributes are collected from any combination of args passed in at
        runtime, environment variables, or a global great_expectations.conf file (in order of precedence).

        If provided as explicit arguments, ge_cloud_base_url, ge_cloud_access_token and
        ge_cloud_organization_id will use runtime values instead of environment variables or conf files.

        Args:
            ge_cloud_base_url: Optional, you may provide this alternatively via
                environment variable GE_CLOUD_BASE_URL or within a config file.
            ge_cloud_access_token: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ACCESS_TOKEN or within a config file.
            ge_cloud_organization_id: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ORGANIZATION_ID or within a config file.

        Returns:
            GeCloudConfig

        Raises:
            GeCloudError if a GE Cloud variable is missing
        """
        ge_cloud_config_dict = cls._get_ge_cloud_config_dict(
            ge_cloud_base_url=ge_cloud_base_url,
            ge_cloud_access_token=ge_cloud_access_token,
            ge_cloud_organization_id=ge_cloud_organization_id,
        )

        missing_keys = []
        for key, val in ge_cloud_config_dict.items():
            if not val:
                missing_keys.append(key)
        if len(missing_keys) > 0:
            missing_keys_str = [f'"{key}"' for key in missing_keys]
            global_config_path_str = [
                f'"{path}"' for path in super().GLOBAL_CONFIG_PATHS
            ]
            raise DataContextError(
                f"{(', ').join(missing_keys_str)} arg(s) required for ge_cloud_mode but neither provided nor found in "
                f"environment or in global configs ({(', ').join(global_config_path_str)})."
            )

        base_url = ge_cloud_config_dict[GECloudEnvironmentVariable.BASE_URL]
        assert base_url is not None
        access_token = ge_cloud_config_dict[GECloudEnvironmentVariable.ACCESS_TOKEN]
        organization_id = ge_cloud_config_dict[
            GECloudEnvironmentVariable.ORGANIZATION_ID
        ]

        return GeCloudConfig(
            base_url=base_url,
            access_token=access_token,
            organization_id=organization_id,
        )

    @classmethod
    def _get_ge_cloud_config_dict(
        cls,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> Dict[GECloudEnvironmentVariable, Optional[str]]:
        ge_cloud_base_url = (
            ge_cloud_base_url
            or CloudDataContext._get_global_config_value(
                environment_variable=GECloudEnvironmentVariable.BASE_URL,
                conf_file_section="ge_cloud_config",
                conf_file_option="base_url",
            )
            or "https://app.greatexpectations.io/"
        )
        ge_cloud_organization_id = (
            ge_cloud_organization_id
            or CloudDataContext._get_global_config_value(
                environment_variable=GECloudEnvironmentVariable.ORGANIZATION_ID,
                conf_file_section="ge_cloud_config",
                conf_file_option="organization_id",
            )
        )
        ge_cloud_access_token = (
            ge_cloud_access_token
            or CloudDataContext._get_global_config_value(
                environment_variable=GECloudEnvironmentVariable.ACCESS_TOKEN,
                conf_file_section="ge_cloud_config",
                conf_file_option="access_token",
            )
        )
        return {
            GECloudEnvironmentVariable.BASE_URL: ge_cloud_base_url,
            GECloudEnvironmentVariable.ORGANIZATION_ID: ge_cloud_organization_id,
            GECloudEnvironmentVariable.ACCESS_TOKEN: ge_cloud_access_token,
        }

    def _init_datasource_store(self) -> None:
        from great_expectations.data_context.store.datasource_store import (
            DatasourceStore,
        )

        store_name: str = "datasource_store"  # Never explicitly referenced but adheres
        # to the convention set by other internal Stores
        store_backend: dict = {"class_name": "GeCloudStoreBackend"}
        runtime_environment: dict = {
            "root_directory": self.root_directory,
            "ge_cloud_credentials": self.ge_cloud_config.to_dict(),  # type: ignore[union-attr]
            "ge_cloud_resource_type": GeCloudRESTResource.DATASOURCE,
            "ge_cloud_base_url": self.ge_cloud_config.base_url,  # type: ignore[union-attr]
        }

        datasource_store = DatasourceStore(
            store_name=store_name,
            store_backend=store_backend,
            runtime_environment=runtime_environment,
            serializer=JsonConfigSerializer(schema=datasourceConfigSchema),
        )
        self._datasource_store = datasource_store

    def list_expectation_suite_names(self) -> List[str]:
        """
        Lists the available expectation suite names. If in ge_cloud_mode, a list of
        GE Cloud ids is returned instead.
        """
        return [suite_key.resource_name for suite_key in self.list_expectation_suites()]  # type: ignore[union-attr]

    @property
    def ge_cloud_config(self) -> Optional[GeCloudConfig]:
        return self._ge_cloud_config

    @property
    def ge_cloud_mode(self) -> bool:
        return self._ge_cloud_mode

    def _init_variables(self) -> CloudDataContextVariables:
        ge_cloud_base_url: str = self._ge_cloud_config.base_url
        ge_cloud_organization_id: str = self._ge_cloud_config.organization_id  # type: ignore[union-attr,assignment]
        ge_cloud_access_token: str = self._ge_cloud_config.access_token

        variables = CloudDataContextVariables(
            config=self._project_config,
            ge_cloud_base_url=ge_cloud_base_url,
            ge_cloud_organization_id=ge_cloud_organization_id,
            ge_cloud_access_token=ge_cloud_access_token,
        )
        return variables

    def _construct_data_context_id(self) -> str:
        """
        Choose the id of the currently-configured expectations store, if available and a persistent store.
        If not, it should choose the id stored in DataContextConfig.
        Returns:
            UUID to use as the data_context_id
        """

        # if in ge_cloud_mode, use ge_cloud_organization_id
        return self.ge_cloud_config.organization_id  # type: ignore[return-value,union-attr]

    def get_config_with_variables_substituted(
        self, config: Optional[DataContextConfig] = None
    ) -> DataContextConfig:
        """
        Substitute vars in config of form ${var} or $(var) with values found in the following places,
        in order of precedence: ge_cloud_config (for Data Contexts in GE Cloud mode), runtime_environment,
        environment variables, config_variables, or ge_cloud_config_variable_defaults (allows certain variables to
        be optional in GE Cloud mode).
        """
        if not config:
            config = self.config

        substitutions: dict = self._determine_substitutions()

        ge_cloud_config_variable_defaults = {
            "plugins_directory": self._normalize_absolute_or_relative_path(
                path=DataContextConfigDefaults.DEFAULT_PLUGINS_DIRECTORY.value
            ),
            "usage_statistics_url": DEFAULT_USAGE_STATISTICS_URL,
        }
        for config_variable, value in ge_cloud_config_variable_defaults.items():
            if substitutions.get(config_variable) is None:
                logger.info(
                    f'Config variable "{config_variable}" was not found in environment or global config ('
                    f'{self.GLOBAL_CONFIG_PATHS}). Using default value "{value}" instead. If you would '
                    f"like to "
                    f"use a different value, please specify it in an environment variable or in a "
                    f"great_expectations.conf file located at one of the above paths, in a section named "
                    f'"ge_cloud_config".'
                )
                substitutions[config_variable] = value

        return DataContextConfig(
            **substitute_all_config_variables(
                config, substitutions, self.DOLLAR_SIGN_ESCAPE_STRING
            )
        )

    def create_expectation_suite(
        self,
        expectation_suite_name: str,
        overwrite_existing: bool = False,
        **kwargs: Optional[dict],
    ) -> ExpectationSuite:
        """Build a new expectation suite and save it into the data_context expectation store.

        Args:
            expectation_suite_name: The name of the expectation_suite to create
            overwrite_existing (boolean): Whether to overwrite expectation suite if expectation suite with given name
                already exists.

        Returns:
            A new (empty) expectation suite.
        """
        if not isinstance(overwrite_existing, bool):
            raise ValueError("Parameter overwrite_existing must be of type BOOL")

        existing_suite_names = self.list_expectation_suite_names()
        if expectation_suite_name in existing_suite_names and not overwrite_existing:
            raise ge_exceptions.DataContextError(
                f"expectation_suite '{expectation_suite_name}' already exists. If you would like to overwrite this "
                "expectation_suite, set overwrite_existing=True."
            )

        expectation_suite = ExpectationSuite(
            expectation_suite_name=expectation_suite_name, data_context=self
        )
        key = GeCloudIdentifier(
            resource_type=GeCloudRESTResource.EXPECTATION_SUITE,
        )

        response: Union[bool, GeCloudResourceRef] = self.expectations_store.set(key, expectation_suite, **kwargs)  # type: ignore[func-returns-value]
        if isinstance(response, GeCloudResourceRef):
            expectation_suite.ge_cloud_id = response.ge_cloud_id

        return expectation_suite

    def delete_expectation_suite(
        self,
        expectation_suite_name: Optional[str] = None,
        ge_cloud_id: Optional[str] = None,
    ) -> bool:
        """Delete specified expectation suite from data_context expectation store.

        Args:
            expectation_suite_name: The name of the expectation_suite to create

        Returns:
            True for Success and False for Failure.
        """
        key = GeCloudIdentifier(
            resource_type=GeCloudRESTResource.EXPECTATION_SUITE,
            ge_cloud_id=ge_cloud_id,
        )
        if not self.expectations_store.has_key(key):  # noqa: W601
            raise ge_exceptions.DataContextError(
                f"expectation_suite with id {ge_cloud_id} does not exist."
            )

        return self.expectations_store.remove_key(key)

    def get_expectation_suite(
        self,
        expectation_suite_name: Optional[str] = None,
        include_rendered_content: Optional[bool] = None,
        ge_cloud_id: Optional[str] = None,
    ) -> ExpectationSuite:
        """Get an Expectation Suite by name or GE Cloud ID
        Args:
            expectation_suite_name (str): The name of the Expectation Suite
            include_rendered_content (bool): Whether or not to re-populate rendered_content for each
                ExpectationConfiguration.
            ge_cloud_id (str): The GE Cloud ID for the Expectation Suite.

        Returns:
            An existing ExpectationSuite
        """
        key = GeCloudIdentifier(
            resource_type=GeCloudRESTResource.EXPECTATION_SUITE,
            ge_cloud_id=ge_cloud_id,
        )
        if not self.expectations_store.has_key(key):  # noqa: W601
            raise ge_exceptions.DataContextError(
                f"expectation_suite with id {ge_cloud_id} not found"
            )

        expectations_schema_dict: dict = cast(dict, self.expectations_store.get(key))

        if include_rendered_content is None:
            include_rendered_content = (
                self._determine_if_expectation_suite_include_rendered_content()
            )

        # create the ExpectationSuite from constructor
        expectation_suite = ExpectationSuite(
            **expectations_schema_dict, data_context=self
        )
        if include_rendered_content:
            expectation_suite.render()
        return expectation_suite

    def save_expectation_suite(
        self,
        expectation_suite: ExpectationSuite,
        expectation_suite_name: Optional[str] = None,
        overwrite_existing: bool = True,
        include_rendered_content: Optional[bool] = None,
        **kwargs: Optional[dict],
    ) -> None:
        """Save the provided expectation suite into the DataContext.

        Args:
            expectation_suite: The suite to save.
            expectation_suite_name: The name of this Expectation Suite. If no name is provided, the name will be read
                from the suite.
            overwrite_existing: Whether to overwrite the suite if it already exists.
            include_rendered_content: Whether to save the prescriptive rendered content for each expectation.

        Returns:
            None
        """
        id = (
            str(expectation_suite.ge_cloud_id)
            if expectation_suite.ge_cloud_id
            else None
        )
        key = GeCloudIdentifier(
            resource_type=GeCloudRESTResource.EXPECTATION_SUITE,
            ge_cloud_id=id,
            resource_name=expectation_suite.expectation_suite_name,
        )

        if not overwrite_existing:
            self._validate_suite_unique_constaints_before_save(key)

        self._evaluation_parameter_dependencies_compiled = False
        include_rendered_content = (
            self._determine_if_expectation_suite_include_rendered_content(
                include_rendered_content=include_rendered_content
            )
        )
        if include_rendered_content:
            expectation_suite.render()

        response = self.expectations_store.set(key, expectation_suite, **kwargs)  # type: ignore[func-returns-value]
        if isinstance(response, GeCloudResourceRef):
            expectation_suite.ge_cloud_id = response.ge_cloud_id

    def _validate_suite_unique_constaints_before_save(
        self, key: GeCloudIdentifier
    ) -> None:
        ge_cloud_id = key.ge_cloud_id
        if ge_cloud_id:
            if self.expectations_store.has_key(key):  # noqa: W601
                raise ge_exceptions.DataContextError(
                    f"expectation_suite with GE Cloud ID {ge_cloud_id} already exists. "
                    f"If you would like to overwrite this expectation_suite, set overwrite_existing=True."
                )

        suite_name = key.resource_name
        existing_suite_names = self.list_expectation_suite_names()
        if suite_name in existing_suite_names:
            raise ge_exceptions.DataContextError(
                f"expectation_suite '{suite_name}' already exists. If you would like to overwrite this "
                "expectation_suite, set overwrite_existing=True."
            )

    @property
    def root_directory(self) -> Optional[str]:
        """The root directory for configuration objects in the data context; the location in which
        ``great_expectations.yml`` is located.

        Why does this exist in AbstractDataContext? CloudDataContext and FileDataContext both use it

        """
        return self._context_root_directory

    def add_checkpoint(
        self,
        name: str,
        config_version: Optional[Union[int, float]] = None,
        template_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
        run_name_template: Optional[str] = None,
        expectation_suite_name: Optional[str] = None,
        batch_request: Optional[dict] = None,
        action_list: Optional[List[dict]] = None,
        evaluation_parameters: Optional[dict] = None,
        runtime_configuration: Optional[dict] = None,
        validations: Optional[List[dict]] = None,
        profilers: Optional[List[dict]] = None,
        # Next two fields are for LegacyCheckpoint configuration
        validation_operator_name: Optional[str] = None,
        batches: Optional[List[dict]] = None,
        # the following four arguments are used by SimpleCheckpoint
        site_names: Optional[Union[str, List[str]]] = None,
        slack_webhook: Optional[str] = None,
        notify_on: Optional[str] = None,
        notify_with: Optional[Union[str, List[str]]] = None,
        ge_cloud_id: Optional[str] = None,
        expectation_suite_ge_cloud_id: Optional[str] = None,
        default_validation_id: Optional[str] = None,
    ) -> "Checkpoint":
        """
        See `AbstractDataContext.add_checkpoint` for more information.
        """

        from great_expectations.checkpoint.checkpoint import Checkpoint

        checkpoint: Checkpoint = Checkpoint.construct_from_config_args(
            data_context=self,
            checkpoint_store_name=self.checkpoint_store_name,  # type: ignore[arg-type]
            name=name,
            config_version=config_version,
            template_name=template_name,
            module_name=module_name,
            class_name=class_name,
            run_name_template=run_name_template,
            expectation_suite_name=expectation_suite_name,
            batch_request=batch_request,
            action_list=action_list,
            evaluation_parameters=evaluation_parameters,
            runtime_configuration=runtime_configuration,
            validations=validations,
            profilers=profilers,
            # Next two fields are for LegacyCheckpoint configuration
            validation_operator_name=validation_operator_name,
            batches=batches,
            # the following four arguments are used by SimpleCheckpoint
            site_names=site_names,
            slack_webhook=slack_webhook,
            notify_on=notify_on,
            notify_with=notify_with,
            ge_cloud_id=ge_cloud_id,
            expectation_suite_ge_cloud_id=expectation_suite_ge_cloud_id,
            default_validation_id=default_validation_id,
        )

        checkpoint_config = self.checkpoint_store.create(
            checkpoint_config=checkpoint.config
        )

        checkpoint = Checkpoint.instantiate_from_config_with_runtime_args(
            checkpoint_config=checkpoint_config, data_context=self  # type: ignore[arg-type]
        )
        return checkpoint
