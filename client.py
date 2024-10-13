import socket
import json
import time

class Client:
    def __init__(self, config_file='client_config.json'):
        self.master_address = None
        self.master_port = None
        self.client_socket = None
        self.retry_attempts = 5  # Set max retry attempts or -1 for infinite retries
        self.retry_delay = 3  # Seconds to wait before retrying
        self.temp_file_path = 'temp_output_file.txt'  # Path to store the temporary file
        self.load_config(config_file)

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as file:
                config = json.load(file)
            self.master_address = config['master_server']['address']
            self.master_port = config['master_server']['port']
            print(f"Configuration loaded from {config_file}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config file: {e}")
    
    def connect_to_master(self):
        attempts = 0
        socket_timeout = 5  # Timeout in seconds for each connection attempt
        while self.retry_attempts == -1 or attempts < self.retry_attempts:
            try:
                # Create a new socket for each attempt
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(socket_timeout)  # Set connection timeout
                print(f"Attempting to connect to Master Server at {self.master_address}:{self.master_port} (Attempt {attempts + 1})")
                # Attempt to connect to the master server
                self.client_socket.connect((self.master_address, self.master_port))
                print(f"Connected to Master Server at {self.master_address}:{self.master_port}")
                return  # Exit function after successful connection
            except socket.timeout as e:
                print(f"Connection timed out after {socket_timeout} seconds. Retrying...")
                attempts += 1
                error_code = e.errno
                print(f"Error connecting to Master Server: {e}, Error Code: {error_code}")
                if self.retry_attempts != -1 and attempts >= self.retry_attempts:
                    print(f"Max retry attempts reached. Unable to connect to Master Server.")
                    return
                print(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
        print("Failed to connect to the Master Server after all attempts.")

    def request_file(self, file_name):
        try:
            # Step 1: Send file name request to the Master Server
            self.client_socket.sendall(file_name.encode())
            print(f"Requested file '{file_name}' from Master Server")
            
            # Step 2: Receive the chunk server address from the Master Server
            chunk_server_address = self.client_socket.recv(4096).decode().strip()
            print(f"Received chunk server address from Master Server: {chunk_server_address}")
            
            # Check if chunk_server_address is in the format 'host:port'
            if ':' not in chunk_server_address:
                print(f"Invalid chunk server address format: {chunk_server_address}")
                return

            # Step 3: Retrieve the file from the specified chunk server
            self.retrieve_file_from_chunk_server(file_name, chunk_server_address)

        except socket.error as e:
            print(f"Error sending request to Master Server: {e}")

    def retrieve_file_from_chunk_server(self, file_name, chunk_server_address):
        try:
            # Split the chunk server address into host and port
            host, port = chunk_server_address.split(':')
            chunk_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            chunk_socket.connect((host, int(port)))

            # Step 5: Send the file request to the Chunk Server
            chunk_socket.sendall(file_name.encode())
            print(f"Requested file '{file_name}' from Chunk Server at {chunk_server_address}")

            # Step 6: Receive the file data from the Chunk Server
            with open(self.temp_file_path, 'wb') as temp_file:  # Open the file in binary mode
                while True:
                    file_data = chunk_socket.recv(4096)  # Receive file in chunks of 4096 bytes
                    if not file_data:
                        print("No more data received from the Chunk Server.")
                        break  # End of file transfer
                    temp_file.write(file_data)  # Write received binary data to the temp file
                print(f"File successfully written to {self.temp_file_path}")

            chunk_socket.close()

        except socket.error as e:
            print(f"Error retrieving file from Chunk Server: {e}")

# Define a handler function with a while True loop
def client_handler():
    # Load client configuration from 'mserver_config.json'
    client = Client("mserver_config.json")
    
    # Keep trying to connect to the master and request files
    while True:
        # Connect to the Master Server
        client.connect_to_master()
        
        # Request a file from the Master Server (user input)
        file_name = input("Enter the file name you want to request (or 'exit' to quit): ").strip()
        if file_name.lower() == 'exit':
            print("Exiting client.")
            break

        client.request_file(file_name)


# Main function to call the handler
if __name__ == "__main__":
    client_handler()
