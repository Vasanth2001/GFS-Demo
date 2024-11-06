import socket
import threading
import json
import time

class MasterServer:
    def __init__(self, config_file='mserver_config.json'):
        self.master_address = None
        self.master_port = None
        self.chunk_servers = []  # List to hold chunk server information
        self.server_loads = {}  # Track server loads
        self.server_status = {}  # Track server health status
        self.file_chunk_mapping = {}  # Map files to primary chunk servers
        self.load_config(config_file)
        self.init_server()
        self.start_health_check()  # Start the health check thread

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as file:
                config = json.load(file)
            self.master_address = config['master_server']['address']
            self.master_port = config['master_server']['port']
            self.chunk_servers = config['chunk_servers']  # Load chunk servers as a list

            # Initialize load and status for each server
            for server in self.chunk_servers:
                server_key = server['name']  # Unique identifier for the server
                self.server_loads[server_key] = 0  # Initialize load for each server
                self.server_status[server_key] = True  # Initially mark servers as healthy
            
            print(f"Configuration loaded from {config_file}")

            # Load file-to-primary mappings from the file metadata
            self.load_file_chunk_mapping()
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"Error loading config file: {e}")
            raise

    def load_file_chunk_mapping(self):
        try:
            with open("files_metadata.json", "r") as f:
                files_metadata = json.load(f)
            
            for file_name, file_info in files_metadata.items():
                primary = file_info.get("primary")
                if primary:
                    # Map file to primary server address
                    primary_server = next(
                        (server for server in self.chunk_servers if server["name"] == primary),
                        None
                    )
                    if primary_server:
                        self.file_chunk_mapping[file_name] = f"{primary_server['address']}:{primary_server['port']}"
            print("File-to-primary mappings initialized:", self.file_chunk_mapping)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading file metadata: {e}")

    def init_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.master_address, self.master_port))
            self.server_socket.listen(5)
            print(f"Master Server started at {self.master_address}:{self.master_port}")

            while True:
                conn, addr = self.server_socket.accept()
                print(f"Connected by {addr}")
                client_thread = threading.Thread(target=self.handle_client, args=(conn,))
                client_thread.start()
        except Exception as e:
            print(f"Error starting Master Server: {e}")

    def handle_client(self, conn):
        try:
            # Receive request from the client
            data = conn.recv(4096)
            if not data:
                print("No data received from client.")
                return

            # Parse the client request
            request = json.loads(data.decode('utf-8'))
            request_type = request.get("type")
            file_name = request.get("file_name")

            if request_type == "read":
                # Handle read request
                print(f"Received read request for file: {file_name}")
                chunk_server_address = self.get_chunk_server_for_file(file_name, is_write=False)
                if chunk_server_address:
                    conn.sendall(chunk_server_address.encode())
                    print(f"Sent chunk server address to client: {chunk_server_address}")
                else:
                    print(f"No chunk server found for file: {file_name}")
                    conn.sendall(b"Error: File not found")

            elif request_type == "write":
                print(f"Received write request for file: {file_name}")
                chunk_server_address = self.get_chunk_server_for_file(file_name, is_write=True)
                if chunk_server_address:
                    response = json.dumps({"address": chunk_server_address.split(":")[0],
                                           "port": int(chunk_server_address.split(":")[1])})
                    conn.sendall(response.encode())
                    print(f"Sent primary server address to client: {chunk_server_address}")
                else:
                    print("No available chunk servers to assign as primary.")
                    conn.sendall(b"Error: No available chunk server for writing.")

        except Exception as e:
            print(f"Error handling client request: {e}")
        finally:
            conn.close()

    def get_chunk_server_for_file(self, file_name, is_write=False):
        if is_write:
            # Check if there's already a primary for this file
            primary_address = self.file_chunk_mapping.get(file_name)
            if not primary_address:
                # Elect a new primary server if none exists
                primary_server = self.select_primary_server(file_name)
                if primary_server:
                    primary_address = f"{primary_server['address']}:{primary_server['port']}"
                    self.file_chunk_mapping[file_name] = primary_address
                    print(f"Primary server for '{file_name}' selected: {primary_address}")
                    self.notify_primary_server(primary_server, file_name)
            return primary_address
        else:
            # For read requests, return any available server
            return self.select_any_server(file_name)

    def select_primary_server(self, file_name):
        # Select a healthy server with the lowest load
        available_servers = [server for server in self.chunk_servers if self.server_status[server['name']]]
        if available_servers:
            return min(available_servers, key=lambda server: self.server_loads[server['name']])
        return None

    def notify_primary_server(self, primary_server, file_name):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((primary_server['address'], primary_server['port']))
                notification = json.dumps({"type": "primary_assignment", "file_name": file_name})
                s.sendall(notification.encode())
                print(f"Primary server {primary_server['name']} notified for file: {file_name}")
        except Exception as e:
            print(f"Failed to notify primary server {primary_server['name']}: {e}")

    def select_any_server(self, file_name):
        # Select any server to handle the read request
        available_servers = [server for server in self.chunk_servers if self.server_status[server['name']]]
        if available_servers:
            least_loaded_server = min(available_servers, key=lambda server: self.server_loads[server['name']])
            self.server_loads[least_loaded_server['name']] += 1
            return f"{least_loaded_server['address']}:{least_loaded_server['port']}"
        return None

    def start_health_check(self):
        health_check_thread = threading.Thread(target=self.check_server_health, daemon=True)
        health_check_thread.start()

    def check_server_health(self):
        while True:
            for server in self.chunk_servers:
                server_name = server['name']
                server_address = (server['address'], server['port'])
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect(server_address)
                    s.close()
                    self.server_status[server_name] = True
                except Exception:
                    self.server_status[server_name] = False
                    print(f"Server {server_name} is down.")
            time.sleep(10)  # Check every 10 seconds

def client_handler():
    master_server = MasterServer(config_file='mserver_config.json')

if __name__ == "__main__":
    client_handler()
