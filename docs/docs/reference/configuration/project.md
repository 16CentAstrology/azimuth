# Project Config

The project configuration contains mainly mandatory fields that specify the dataset to load in
Azimuth and details about the way it is handled by the app.

=== "Class Definition"

    ```python
    from typing import Optional

    from pydantic import BaseSettings, Field

    from azimuth.config import ColumnConfiguration, CustomObject

    class ProjectConfig(BaseSettings):
        name: str = "New project"
        dataset: CustomObject
        columns: ColumnConfiguration = ColumnConfiguration()
        rejection_class: Optional[str] = "REJECTION_CLASS"
    ```

=== "Config Example"

    ```json
    {
      "name": "Banking77 Model v4",
      "dataset": {
        "class_name": "datasets.load_dataset",
        "args": [
          "banking77"
        ]
      },
      "columns": {
        "text_input": "text",
        "label": "target"
      },
      "rejection_class": "NA",
    }
    ```

## Name

🟡 **Default value**: `New project`

**Environment Variable**: `NAME`

Any name can be set for the config. For example, it can represent the name of the dataset and/or the
model. Ex: `Banking77 Model v4`.

## Dataset

🔴 **Mandatory field**

To define which dataset to load in the application, Azimuth
uses [:material-link: Custom Objects](../custom-objects/index.md).

If the dataset is already on HuggingFace, you can use
the [`datasets.load_dataset`](https://huggingface.co/docs/datasets/loading) from HF, as shown in the
example below. If you have your own dataset, you will need to create your own custom object, as
explained in [:material-link: Defining Dataset](../custom-objects/dataset.md).

=== "Custom Object Definition"

    ```python
    from typing import Any, Dict, List, Optional, Union

    from pydantic import BaseModel, Field

    class CustomObject(BaseModel):
        class_name: str # (1)
        args: List[Union["CustomObject", Any]] = []
        kwargs: Dict[str, Union["CustomObject", Any]] = {}
        remote: Optional[str] = None # (2)
    ```

    1. Name of the function or class that is located in `remote`. `args` and `kwargs` will be sent to the function/class.
    2. Absolute path to class. `class_name` needs to be accessible from this path.

=== "Config Example with HF"

    Example to load [`banking77`](https://huggingface.co/datasets/banking77) from HF.

    ```json
    {
      "dataset": {
        "class_name": "datasets.load_dataset",
        "args": [
          "banking77"
        ]
      }
    }
    ```

## Columns

🟡 **Default value**: `ColumnConfiguration()`

All dataset column names are configurable. The mandatory columns and their descriptions are as
follows:

| Field name | Default   | Description                                                       |
|------------|-----------|-------------------------------------------------------------------|
| `text_input` | `utterance` | The preprocessed utterance.                                       |
| `label`      | `label`     | The class label for the utterance, as type `datasets.ClassLabel`. |
| `persistent_id` | `row_idx` | A unique identifier for each utterance, as type `datasets.Value("int16")` or `datasets.Value("string")`. |

=== "Class Definition"

    ```python
    from pydantic import BaseModel

    class ColumnConfiguration(BaseModel):
        text_input: str = "utterance" # (1)
        raw_text_input: str = "utterance_raw" # (2)
        label: str = "label" # (3)
        failed_parsing_reason: str = "failed_parsing_reason" # (4)
        persistent_id: str = "row_idx" # (5)
    ```

    1. Column for the text input that will be send to the pipeline.
    2. Optional column for the raw text input (before any pre-processing). Unused at the moment.
    3. Features column for the label
    4. Optional column to specify whether an example has failed preprocessing. Unused at the moment.
    5. Column with a unique identifier for every example that should be persisted if the dataset is modified, such as if new examples are added or if examples are modified or removed.

=== "Config Example"

    Example to override the default column values.

    ```json
    {
      "columns": {
        "text_input": "text",
        "label": "target"
      }
    }
    ```

## Rejection class

🟡 **Default value**: `REJECTION_CLASS`

The field `rejection_class` requires the class to be present in the dataset. If your dataset doesn't
have a rejection class, set the value to `null`. More details on the rejection class are available
in [Prediction Outcomes](../../key-concepts/outcomes.md).

--8<-- "includes/abbreviations.md"
