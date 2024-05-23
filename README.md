# AWS Tag Analyzer

AWS Tag Analyzer is a Python script that fetches resource tags from multiple AWS environments and generates CSV reports. It supports filtering of tags based on specified criteria and provides both detailed and summary reports.

## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Outputs](#outputs)
- [Logging](#logging)

## Requirements
- Python 3.6+
- AWS CLI
- IAM user with sufficient permissions to read resource tags

## Installation
1. **Clone the repository**:
    ```sh
    git clone https://github.com/yourusername/aws-tag-analyzer.git
    cd aws-tag-analyzer
    ```

2. **Create a virtual environment** (optional but recommended):
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install required Python packages**:
    ```sh
    pip install -r requirements.txt
    ```

## Configuration
1. **Create a configuration file** (`config.yaml`):
    ```yaml
    input_dir: input
    output_dir: output
    focus_file: focus.yaml
    ```

2. **Create AWS credentials files** in the `input` directory (e.g., `dev_input.ini`):
    ```ini
    export AWS_ACCESS_KEY_ID="your_access_key_id"
    export AWS_SECRET_ACCESS_KEY="your_secret_access_key"
    export AWS_SESSION_TOKEN="your_session_token"
    ```

3. **Create a focus file** (`focus.yaml`) for filtering tags:
    ```yaml
    include_keys: ["customer_function"]
    exclude_keys: []
    include_values: []
    exclude_values: ["platform"]
    ```

## Usage
1. **Run the script**:
    ```sh
    python analyze.py config.yaml
    ```

2. **Optional arguments**:
    - `config_file`: Path to the YAML configuration file (default: `config.yaml`).

## Outputs
The script generates the following CSV files in the specified `output` directory:
1. **Regular Environment CSV**: `<env>_tags.csv`
   - Contains all resources and their tags for each environment.

2. **Focused Environment CSV**: `<env>_focused_tags.csv`
   - Contains filtered resources based on the focus file.

3. **Summary CSV**: `summary_tags.csv`
   - Provides an overview of tags across all environments.

4. **Focused Summary CSV**: `focused_summary_tags.csv`
   - Provides detailed statistics on the focused tags.

## Logging
The script uses Python's built-in logging module to capture detailed information and errors. Logs are output to the console with different levels of verbosity.

## Contributing
Feel free to submit issues or pull requests if you have suggestions or improvements.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
