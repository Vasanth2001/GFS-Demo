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
            # Step 1: Receive and decode the request from the client
            data = client_socket.recv(4096).decode().strip()
            request = json.loads(data)  # Parse JSON request
            request_type = request.get("type")
            file_name = request.get("file_name")

            # Handle write requests differently based on the server type
            if request_type == "write":
                content = request.get("data")
                server_type = request.get("server")  # 'primary' or 'secondary'
                print(f"Received write request for {file_name} with content '{content}'")

                # Primary server handles write and forwards to secondary servers
                if server_type == "primary":
                    print(f"Primary server {self.server_id} handling write to {file_name} with content '{content}'")

                    # Append data to the file locally
                    success = self.append_to_file(file_name, content)

                    if success:
                        # Deduce secondaries by excluding the current server from the replicas
                        secondaries = self.get_secondaries(file_name)
                        print(f"Secondaries for {file_name}: {secondaries}")

                        # Forward the write to secondaries
                        secondary_status = []
                        for secondary_address in secondaries:
                            try:
                                sec_host, sec_port = secondary_address
                                secondary_status.append(self.forward_to_secondary(sec_host, sec_port, file_name, content))
                            except Exception as e:
                                print(f"Error forwarding to secondary {secondary_address}: {e}")
                                secondary_status.append(False)

                        # Verify if all secondaries succeeded
                        if all(secondary_status):
                            client_socket.sendall(b"Write success")
                            print("Write committed successfully to primary and all secondaries")
                        else:
                            # Rollback if any secondary fails
                            self.rollback_file(file_name)
                            for sec_addr in secondaries:
                                self.rollback_secondary(sec_addr, file_name)
                            client_socket.sendall(b"Write failed")
                            print("Write failed; rolled back changes")
                    else:
                        client_socket.sendall(b"Write failed")
                        print("Write failed locally")

                # Secondary server forwards the write to its file (it does not initiate writes)
                elif server_type == "secondary":
                    print(f"Secondary server {self.server_id} received write request for {file_name} with content '{content}'")
                    success = self.append_to_file(file_name, content)
                    if success:
                        client_socket.sendall(b"Write success")
                        print(f"Write successful on secondary server {self.server_id}")
                    else:
                        client_socket.sendall(b"Write failed")
                        print(f"Write failed on secondary server {self.server_id}")

            # Handle read requests (not server_type dependent)
            if request_type == "read":
                print(f"Client requested to read: {file_name}")
                if file_name in self.files and os.path.exists(self.files[file_name]):
                    # Open and send the file contents in chunks
                    try:
                        with open(self.files[file_name], 'rb') as f:
                            while chunk := f.read(4096):
                                client_socket.sendall(chunk)
                        print(f"Sent file {file_name} to client")
                    except Exception as e:
                        print(f"Error reading file {file_name}: {e}")
                        client_socket.sendall(f"Error: Could not read file {file_name}".encode())
                else:
                    error_message = f"Error: File {file_name} not found on server."
                    print(error_message)
                    client_socket.sendall(error_message.encode())

            else:
                print(f"Unknown request type {request_type}")

        except Exception as e:
            print(f"Error handling client request: {e}")
        finally:
            client_socket.close()


    def append_to_file(self, file_name, content):
        try:
            file_path = os.path.join(f"{self.server_id}_files", file_name)
            # Open the file in append mode
            with open(file_path, 'a') as f:
                f.write(content)
            print(f"Write successful on {file_name}")
            return True
        except Exception as e:
            print(f"Error writing to {file_name}: {e}")
            return False

    def get_secondaries(self, file_name):
        try:
            # Load file metadata
            with open("files_metadata.json", "r") as f:
                file_metadata = json.load(f)

            if file_name in file_metadata:
                replicas = file_metadata[file_name]["replicas"]
                # Exclude the current server from the list of replicas
                secondaries = [replica for replica in replicas if replica != self.server_id]
                
                # Retrieve full server address (host, port) from servers.json for each secondary server
                secondary_addresses = []
                with open("servers.json", "r") as servers_file:
                    servers_data = json.load(servers_file)
                    
                    # Get the actual address (IP and port) for each secondary server
                    for secondary in secondaries:
                        if secondary in servers_data:
                            secondary_addresses.append(tuple(servers_data[secondary]))
                        else:
                            print(f"Warning: No address found for {secondary} in servers.json")

                return secondary_addresses
            else:
                print(f"Error: {file_name} not found in metadata")
                return []
        except Exception as e:
            print(f"Error getting secondaries: {e}")
            return []

    def forward_to_secondary(self, host, port, file_name, content):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sec_sock:
                sec_sock.connect((host, port))
                write_data = {
                    "type": "write",
                    "file_name": file_name,
                    "data": content,
                    "server": "secondary"
                }
                sec_sock.sendall(json.dumps(write_data).encode())

                response = sec_sock.recv(4096).decode()
                return response == "Write success"
        except Exception as e:
            print(f"Error communicating with secondary: {e}")
            return False

    def rollback_file(self, file_name):
        # Logic to rollback changes locally (e.g., restore from a backup or clear)
        print(f"Rolling back changes to {file_name} on this server")

    def rollback_secondary(self, sec_addr, file_name):
        try:
            sec_host, sec_port = sec_addr
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sec_sock:
                sec_sock.connect((sec_host, int(sec_port)))
                rollback_request = json.dumps({"type": "rollback", "file_name": file_name})
                sec_sock.sendall(rollback_request.encode())
        except Exception as e:
            print(f"Error rolling back on secondary {sec_addr}: {e}")


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
