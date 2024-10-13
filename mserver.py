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
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"Error loading config file: {e}")
            raise

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
            data = conn.recv(4096)
            if not data:
                print("No data received from client.")
                return
            file_name = data.decode('utf-8').strip()
            print(f"Received file request from client: {file_name}")

            # Get the chunk server address for the requested file
            chunk_server_address = self.get_chunk_server_for_file(file_name)
            if chunk_server_address:
                conn.sendall(chunk_server_address.encode())
                print(f"Sent chunk server address to client: {chunk_server_address}")
            else:
                print(f"No chunk server found for file: {file_name}")
                conn.sendall(b"Error: File not found")
        except Exception as e:
            print(f"Error handling client request: {e}")
        finally:
            conn.close()

    def get_chunk_server_for_file(self, file_name):
        # For this example, we assume each file is replicated on all chunk servers.
        # You can implement your own logic to determine which servers have the file.
        available_servers = [server for server in self.chunk_servers if self.server_status[server['name']]]
        
        if available_servers:
            least_loaded_server = min(available_servers, key=lambda server: self.server_loads[server['name']])
            self.server_loads[least_loaded_server['name']] += 1
            server_address = f"{least_loaded_server['address']}:{least_loaded_server['port']}"
            print(f"Assigned chunk server {least_loaded_server['name']} for file {file_name} (Current load: {self.server_loads[least_loaded_server['name']]})")
            return server_address
        else:
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
                    # Check if the server is reachable (can be done via a ping or a simple socket connection)
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)  # Set timeout for the connection
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
