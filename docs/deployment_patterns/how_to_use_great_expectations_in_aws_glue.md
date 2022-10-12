---
title: How to Use Great Expectations in AWS Glue
---
import Prerequisites from './components/deployment_pattern_prerequisites.jsx'
import Congratulations from '../guides/connecting_to_your_data/components/congratulations.md'

This Guide demonstrates how to set up, initialize and run validations against your data on AWS Glue Spark Job.
We will cover case with RuntimeDataConnector and use S3 as metadata store.

### 0. Pre-requirements

- Configure great_expectations.yaml and upload to your S3 bucket or generate it dynamically from code
```yaml file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns_great_expectations.yaml#L1-L67
```


### 1. Install Great Expectations
You need to add to your AWS Glue Spark Job Parameters to install great expectations module. Glue at least v2
```bash
  — additional-python-modules great_expectations
```
Then import necessary libs:
```python file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns.py#L1-L13
```

### 2. Set up Great Expectations
Here we initialize a Spark and Glue, and read great_expectations.yaml
```python file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns.py#L15-L22
```

### 3. Connect to your data
```python file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns.py#L24-L43
```

### 4. Create Expectations
```python file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns.py#L45-L62
```

### 5. Validate your data
```python file=../../tests/integration/docusaurus/deployment_patterns/aws_glue_deployment_patterns.py#L64-L78
```

### 6. Congratulations!
Your data docs built on S3 and you can see index.html at the bucket


<details>
  <summary>This documentation has been contributed by Bogdan Volodarskiy from Provectus</summary>
  <div>
    <p>
      Our links:
    </p>
    <ul>
      <li> <a href="https://www.linkedin.com/in/bogdan-volodarskiy-652498108/">Author's Linkedin</a> </li>
      <li> <a href="https://medium.com/@bvolodarskiy">Author's Blog</a> </li>
      <li> <a href="https://provectus.com/">About Provectus</a> </li>
      <li> <a href="https://provectus.com/data-quality-assurance/">About Provectus Data QA Expertise</a> </li>
</ul>
  </div>
</details>
