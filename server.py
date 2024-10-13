import socket
import json
import os
import threading


class Server:
    def __init__(self, server_id):
        self.server_id = server_id
        self.files = {}
        self.server_address = None  # Placeholder for server IP
        self.server_port = None     # Placeholder for server port
        self.load_server_files()

    def load_server_files(self):
        # Load files from the corresponding directory based on server_id
        directory = f"{self.server_id}_files"  # E.g., "server1_files"
        
        # Load files from files_metadata.json
        with open("files_metadata.json", "r") as f:
            file_metadata = json.load(f)

        # For each file in the metadata, check if this server manages it
        for file_name, file_info in file_metadata.items():
            if self.server_id in file_info["replicas"]:
                # File path is inside the server's specific directory
                file_path = os.path.join(directory, file_name)
                if os.path.exists(file_path):
                    self.files[file_name] = file_path
        
        print(f"Server {self.server_id} managing files: {list(self.files.keys())}")

    def start(self):
        try:
            # Create the server socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind((self.server_address, self.server_port))  # Corrected the attribute names
            server_socket.listen(5)
            print(f"Server {self.server_id} listening on {self.server_address}:{self.server_port}")  # Corrected print statement

            # Accept clients in a loop
            while True:
                client_socket, addr = server_socket.accept()
                print(f"Connection from {addr}")
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.start()

        except Exception as e:
            print(f"Error starting server {self.server_id}: {e}")  # Corrected the attribute name
        finally:
            server_socket.close()
    
    def handle_client(self, client_socket):
        try:
            file_name = client_socket.recv(4096).decode().strip()
            print(f"Client requested: {file_name}")
            
            # Check if the file is managed by this server
            if file_name in self.files and os.path.exists(self.files[file_name]):
                with open(self.files[file_name], 'r') as f:
                    file_data = f.read()
                client_socket.sendall(file_data.encode())
                print(f"Sent file {file_name} to client")
            else:
                client_socket.sendall(f"File {file_name} not found on this server.".encode())
                print(f"File {file_name} not found on server")
        except Exception as e:
            print(f"Error handling client request: {e}")
        finally:
            client_socket.close()

def start_server_thread(server_id, server_address, server_port):
    server = Server(server_id)
    server.server_address = server_address  # Set the correct server address
    server.server_port = server_port        # Set the correct server port
    server.start()

if __name__ == "__main__":
    # Load the server configuration from server_config.json
    with open("mserver_config.json", "r") as config_file:
        config_data = json.load(config_file)
    
    # Get the list of chunk servers
    chunk_servers = config_data["chunk_servers"]
    
    # Start each server in its own thread
    threads = []
    for server_info in chunk_servers:
        server_id = server_info["name"]
        server_address = server_info["address"]
        server_port = server_info["port"]

        # Create and start a thread for each server
        thread = threading.Thread(target=start_server_thread, args=(server_id, server_address, server_port))
        thread.start()
        threads.append(thread)

    # Wait for all threads to complete (optional)
    for thread in threads:
        thread.join()
