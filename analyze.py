import os
import json
import csv
import yaml
import subprocess
import logging
from collections import defaultdict
import pandas as pd
from typing import List, Dict, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_aws_credentials(credential_dir: str) -> Dict[str, Dict[str, str]]:
    """Load AWS credentials from files in the specified directory."""
    logging.info(f"Loading AWS credentials from {credential_dir}")
    credentials = {}
    for filename in os.listdir(credential_dir):
        if filename.endswith(".ini"):
            env_name = filename.split(".")[0]
            creds = {}
            with open(os.path.join(credential_dir, filename), 'r') as file:
                for line in file:
                    if line.startswith("export"):
                        key, value = line.replace("export ", "").strip().split('=', 1)
                        creds[key] = value.strip('"')
            credentials[env_name] = creds
    logging.info(f"Loaded credentials for environments: {', '.join(credentials.keys())}")
    return credentials

def fetch_resource_tags(region: str, max_retries: int = 3) -> List[Dict]:
    """Fetch resource tags using AWS CLI with retry logic for transient errors."""
    resources = []
    next_token = None
    retries = 0

    while True:
        cmd = [
            'aws', 'resourcegroupstaggingapi', 'get-resources',
            '--region', region,
            '--output', 'json'
        ]
        if next_token:
            cmd.extend(['--starting-token', next_token])

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, env=os.environ
        )

        if result.returncode != 0:
            logging.error(f"Error fetching tags: {result.stderr}")
            retries += 1
            if retries >= max_retries:
                raise RuntimeError(f"AWS CLI command failed after {max_retries} retries")
            logging.info(f"Retrying ({retries}/{max_retries})...")
            continue

        logging.debug(f"AWS CLI output: {result.stdout}")
        
        try:
            response = json.loads(result.stdout)
            resources.extend(response.get("ResourceTagMappingList", []))
            next_token = response.get("PaginationToken")
            if not next_token:
                break
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON response: {result.stdout}")
            raise e

    logging.info(f"Fetched {len(resources)} resources from {region}")
    return resources

def filter_tags(tags: List[Dict], filters: Dict) -> List[Dict]:
    """Filter tags based on provided criteria."""
    logging.info(f"Filtering tags with filters: {filters}")
    include_keys = filters.get('include_keys', [])
    exclude_keys = filters.get('exclude_keys', [])
    include_values = filters.get('include_values', [])
    exclude_values = filters.get('exclude_values', [])
    
    def tag_matches(tag):
        key, value = tag['Key'], tag['Value']
        if include_keys and key not in include_keys:
            return False
        if exclude_keys and key in exclude_keys:
            return False
        if include_values and value not in include_values:
            return False
        if exclude_values and value in exclude_values:
            return False
        return True

    filtered_tags = []
    for resource in tags:
        filtered_resource_tags = [tag for tag in resource['Tags'] if tag_matches(tag)]
        if filtered_resource_tags:
            filtered_resource = resource.copy()
            filtered_resource['Tags'] = filtered_resource_tags
            filtered_tags.append(filtered_resource)
    
    logging.info(f"Filtered down to {len(filtered_tags)} resources")
    return filtered_tags

def json_to_csv(json_data: List[Dict], csv_filename: str, focus_key=None, exclude_values=None):
    """Convert JSON data to CSV."""
    logging.info(f"Writing data to CSV file: {csv_filename}")
    all_tags = set()
    for resource in json_data:
        for tag in resource.get("Tags", []):
            all_tags.add(tag["Key"])
    
    sorted_tags = sorted(list(all_tags))
    if focus_key:
        csv_header = ["Resource ARN", "Resource Type", focus_key]
    else:
        csv_header = ["Resource ARN", "Resource Type"] + sorted_tags

    csv_rows = []
    for resource in json_data:
        resource_arn = resource["ResourceARN"]
        resource_type = resource_arn.split(":")[2]
        row = [resource_arn, resource_type]
        
        tag_values = {tag: 'N/A' for tag in sorted_tags}
        for tag in resource.get("Tags", []):
            if tag["Key"] in tag_values:
                tag_values[tag["Key"]] = tag["Value"]

        if focus_key:
            if tag_values.get(focus_key, 'N/A') in exclude_values:
                continue
            row.append(tag_values.get(focus_key, 'N/A'))
        else:
            row.extend([tag_values[tag] for tag in sorted_tags])
        
        csv_rows.append(row)
    
    with open(csv_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(csv_header)
        csvwriter.writerows(csv_rows)
    logging.info(f"CSV file {csv_filename} written with {len(csv_rows)} rows")

def generate_summary_csv(tag_data: Dict[str, List[Dict]], summary_filename: str):
    """Generate a summary CSV from all environment data."""
    logging.info(f"Generating summary CSV: {summary_filename}")
    all_tags = defaultdict(lambda: defaultdict(set))
    for env, tags in tag_data.items():
        for resource in tags:
            for tag in resource.get("Tags", []):
                all_tags[tag["Key"]][env].add(tag["Value"])

    summary_data = {
        "Tag Key": [],
        **{env: [] for env in tag_data.keys()},
        "Possible Values": []
    }
    for tag, envs in all_tags.items():
        summary_data["Tag Key"].append(tag)
        for env in tag_data.keys():
            summary_data[env].append("yes" if env in envs else "no")
        possible_values = [value for values in envs.values() for value in values]
        summary_data["Possible Values"].append(list(set(possible_values)))
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_filename, index=False)
    logging.info(f"Summary CSV {summary_filename} generated")

def generate_focused_summary_csv(tag_data: Dict[str, List[Dict]], summary_filename: str, filters: Dict):
    """Generate a focused summary CSV from all environment data."""
    logging.info(f"Generating focused summary CSV: {summary_filename}")
    include_keys = set(filters.get('include_keys', []))
    exclude_keys = set(filters.get('exclude_keys', []))
    include_values = set(filters.get('include_values', []))
    exclude_values = set(filters.get('exclude_values', []))

    summary_data = {
        "Environment": [],
        "Focused Tag Key": [],
        "Focused Tag Value": [],
        "Excluded Tag Key": [],
        "Excluded Tag Value": [],
        "Total Resources": [],
        "Resources with Focused Tags": [],
        "Resources Missing Focused Tags": []
    }
    
    for env, tags in tag_data.items():
        total_resources = len(tags)
        focused_resources = 0
        missing_resources = 0
        
        for resource in tags:
            has_focused_tag = False
            for tag in resource.get("Tags", []):
                key, value = tag['Key'], tag['Value']
                if (key in include_keys or value in include_values) and (key not in exclude_keys and value not in exclude_values):
                    has_focused_tag = True
                    break
            if has_focused_tag:
                focused_resources += 1
            else:
                missing_resources += 1
        
        summary_data["Environment"].append(env)
        summary_data["Focused Tag Key"].append(", ".join(include_keys))
        summary_data["Focused Tag Value"].append(", ".join(include_values))
        summary_data["Excluded Tag Key"].append(", ".join(exclude_keys))
        summary_data["Excluded Tag Value"].append(", ".join(exclude_values))
        summary_data["Total Resources"].append(total_resources)
        summary_data["Resources with Focused Tags"].append(focused_resources)
        summary_data["Resources Missing Focused Tags"].append(missing_resources)
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_filename, index=False)
    logging.info(f"Focused summary CSV {summary_filename} generated")

def validate_inputs(input_dir: str, output_dir: str, focus_file: str):
    """Validate the input directory, output directory, and focus file."""
    if not os.path.isdir(input_dir):
        raise ValueError(f"Input directory {input_dir} does not exist.")
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    if focus_file and not os.path.isfile(focus_file):
        raise ValueError(f"Focus file {focus_file} does not exist.")

def process_environment_tags(env: str, creds: Dict, filters: Dict, output_dir: str):
    """Process tags for a specific environment and save to CSV."""
    os.environ['AWS_ACCESS_KEY_ID'] = creds['AWS_ACCESS_KEY_ID']
    os.environ['AWS_SECRET_ACCESS_KEY'] = creds['AWS_SECRET_ACCESS_KEY']
    os.environ['AWS_SESSION_TOKEN'] = creds['AWS_SESSION_TOKEN']
    region = creds.get('AWS_REGION', 'eu-central-1')  # Default to 'eu-central-1' if not specified

    logging.info(f"Fetching tags for environment: {env}")
    tags = fetch_resource_tags(region)

    # Regular environment CSV
    csv_filename = os.path.join(output_dir, f"{env}_tags.csv")
    json_to_csv(tags, csv_filename)
    
    if filters:
        # Focused environment CSV
        focused_csv_filename = os.path.join(output_dir, f"{env}_focused_tags.csv")
        json_to_csv(tags, focused_csv_filename, focus_key=filters.get('include_keys', [None])[0], exclude_values=filters.get('exclude_values', []))

def load_configuration(config_file: str) -> Dict:
    """Load configuration from a YAML file."""
    if not os.path.isfile(config_file):
        raise ValueError(f"Configuration file {config_file} does not exist.")
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

def main(config_file: str):
    config = load_configuration(config_file)
    input_dir = config['input_dir']
    output_dir = config['output_dir']
    focus_file = config.get('focus_file')

    validate_inputs(input_dir, output_dir, focus_file)
    
    credentials = load_aws_credentials(input_dir)
    tag_data = {}
    
    if focus_file:
        with open(focus_file, 'r') as file:
            filters = yaml.safe_load(file)
    else:
        filters = {}
    
    for env, creds in credentials.items():
        process_environment_tags(env, creds, filters, output_dir)
        tag_data[env] = fetch_resource_tags(creds.get('AWS_REGION', 'eu-central-1'))

    # Regular summary CSV
    summary_filename = os.path.join(output_dir, "summary_tags.csv")
    generate_summary_csv(tag_data, summary_filename)
    
    if filters:
        # Focused summary CSV
        focused_summary_filename = os.path.join(output_dir, "focused_summary_tags.csv")
        generate_focused_summary_csv(tag_data, focused_summary_filename, filters)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AWS Tag Analyzer")
    parser.add_argument('config_file', help="YAML configuration file")
    args = parser.parse_args()

    main(args.config_file)
