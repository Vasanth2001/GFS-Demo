import os
import json
import shutil

def load_json_config(config_file):
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
        print(f"Configuration loaded from {config_file}")
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config file: {e}")
        return None

def copy_files_to_replicas(config, main_directory):
    if not os.path.exists(main_directory):
        print(f"Error: Main directory '{main_directory}' does not exist.")
        return

    for file_name, details in config.items():
        file_path = os.path.join(main_directory, file_name)

        # Check if the file exists in the main directory
        if not os.path.exists(file_path):
            print(f"Error: File '{file_name}' not found in the main directory.")
            continue
        
        # Copy the file to each of the replica directories
        replicas = details.get('replicas', [])
        for server in replicas:
            # Create the directory for the server if it doesn't exist
            server_directory = f"{server}_files"
            os.makedirs(server_directory, exist_ok=True)
            
            # Define the destination path
            destination_path = os.path.join(server_directory, file_name)

            # Copy the file
            shutil.copy(file_path, destination_path)
            print(f"Copied '{file_name}' to '{server_directory}'")

def main():
    config_file = "files_metadata.json"  
    main_directory = os.getcwd() 

    # Load the JSON configuration file
    config = load_json_config(config_file)

    if config:
        # Copy the files to the respective replica directories
        copy_files_to_replicas(config, main_directory)

if __name__ == "__main__":
    main()
