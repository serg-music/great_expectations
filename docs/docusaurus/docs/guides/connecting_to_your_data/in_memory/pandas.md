---
title: How to connect to in-memory data in a Pandas dataframe
---

import NextSteps from '../components/next_steps.md'
import Congratulations from '../components/congratulations.md'
import Prerequisites from '../components/prerequisites.jsx'
import WhereToRunCode from '../components/where_to_run_code.md'
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import TechnicalTag from '@site/docs/term_tags/_tag.mdx';

This guide will help you connect to your data that is an in-memory Pandas dataframe.
This will allow you to <TechnicalTag tag="validation" text="Validate" /> and explore your data.

<Prerequisites>

- Have access to data in a Pandas dataframe

</Prerequisites>

## Steps

### 1. Choose how to run the code in this guide

<WhereToRunCode />

### 2. Instantiate your project's DataContext

Import these necessary packages and modules.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py imports"
```

Load your DataContext into memory using the `get_context()` method.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py get_context"
```


### 3. Configure your Datasource

Using this example configuration we configure a `RuntimeDataConnector` as part of our <TechnicalTag tag="datasource" text="Datasource" />, which will take in our in-memory frame.:

<Tabs
  groupId="yaml-or-python"
  defaultValue='yaml'
  values={[
  {label: 'YAML', value:'yaml'},
  {label: 'Python', value:'python'},
  ]}>

<TabItem value="yaml">

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py datasource_yaml"
```

Run this code to test your configuration.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py test_yaml_config"
```

**Note**: Since the Datasource does not have data passed-in until later, the output will show that no `data_asset_names` are currently available. This is to be expected.

</TabItem>
<TabItem value="python">

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_python_example.py datasource_config"
```

Run this code to test your configuration.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_python_example.py test_yaml_config"
```

**Note**: Since the Datasource does not have data passed-in until later, the output will show that no `data_asset_names` are currently available. This is to be expected.

</TabItem>

</Tabs>

### 4. Save the Datasource configuration to your DataContext

Save the configuration into your `DataContext` by using the `add_datasource()` function.

<Tabs
  groupId="yaml-or-python"
  defaultValue='yaml'
  values={[
  {label: 'YAML', value:'yaml'},
  {label: 'Python', value:'python'},
  ]}>

<TabItem value="yaml">

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py add_datasource"
```

</TabItem>

<TabItem value="python">

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_python_example.py add_datasource"
```

</TabItem>

</Tabs>

### 6. Test your new Datasource

Verify your new Datasource by loading data from it into a `Validator` using a `RuntimeBatchRequest`.

:::note The dataframe we are using in this example looks like the following

Please feel free to substitute your data.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py example dataframe"
```
:::

Add the variable containing your dataframe (`df` in this example) to the `batch_data` key under `runtime_parameters` in your `RuntimeBatchRequest`.

```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py batch_request"
```

Then load data into the `Validator`.
```python name="tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py get_validator"
```

<Congratulations />

## Additional Notes

To view the full scripts used in this page, see them on GitHub:

- [pandas_yaml_example.py](https://github.com/great-expectations/great_expectations/blob/develop/tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_yaml_example.py)
- [pandas_python_example.py](https://github.com/great-expectations/great_expectations/blob/develop/tests/integration/docusaurus/connecting_to_your_data/in_memory/pandas_python_example.py)

## Next Steps

<NextSteps />
