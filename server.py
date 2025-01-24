import ipaddress
import pathlib
import psutil
import socket
import threading
import traceback


# Data Type can be of max 10 Characters
# Currently supports (Text/File) -> to implemet POLL
DATA_TYPE_SIZE = 10        


class Server():

    def __init__(self, server_ip: str = None, port: int = 5555, max_connections: int = 1, data_header_size: int = 13, filename_header_size: int = 7):
        """
        Create socket object; bind server to host ip address and port; start listening for incoming connections
        
        :param server: The IP address of the server/host.
        :param port: The port number.
        """

        try:
            self.client_dict = {}
            self.data_header_size = data_header_size
            self.filename_header_size = filename_header_size
            self.download_location = pathlib.Path.cwd() / 'Downloads'
            self.print_received_text = True
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #Avoid TIME-WAIT Period after closing connction
            self.port = port
            self.server_ip = self._get_private_ip_address() if not server_ip else server_ip
            if self.server_ip:
                self.server.bind((self.server_ip, self.port))
                self.server.listen(max_connections)
                print("waiting for a connection. Server started")
                print(f"Server listening on {self.server_ip}, port {self.port}")
            else:
                raise ValueError("You are not connected to any private network")
        except socket.error as e:
            print('Socket error while initializing server:', traceback.format_exc())
        except Exception as e:
            print('Unexpected error while initializing server:', traceback.format_exc())


    def _get_private_ip_address(self):
        try:
            for addrs in psutil.net_if_addrs().values():
                for addr in addrs:
                    # Check for IPv4 addresses that are not loopback
                    if addr.family == socket.AF_INET:
                        ip = ipaddress.ip_address(addr.address)
                        if ip.is_private and not ip.is_loopback:
                            return addr.address
        except Exception as e:
            print("Private IP address fetching Error: ", traceback.format_exc())
            return None
    

    def send_data(self, sender_conn, receiver, data):
        """:param receiver: receiver username (must be None if data is being sent back to sender)"""

        try:
            # Select Receiver (send to self if receiver is None)
            receiver_client = self.client_dict.get(receiver) if receiver else None
            if receiver_client:
                conn = receiver_client
            else:
                conn = sender_conn
                # data = f"{receiver} not found"

            # send header with msg length
            if not isinstance(data, bytes):
                encoded_data = data.encode("utf-8")
            else:
                encoded_data = data
            data_length = len(encoded_data)

            header = f"{data_length:<{(self.data_header_size)}}".encode("utf-8")
            conn.sendall(header)

            # Send the actual data
            conn.sendall(encoded_data)
        except socket.error as e:
            print("Server Data Sending Socket Error: ", traceback.format_exc())
        except Exception as e:
            print("Server Data Sending General Error: ",  traceback.format_exc())


    def receive_data(self, conn):
        try:
            # Receive Data Size
            data_size = conn.recv(self.data_header_size)
            # If empty data is sent assume client socket is closed
            if not data_size:
                print("Client Disconected")
                return
            
            data_length = int(data_size.decode().strip())
            print(f"Expecting {data_length} bytes of data.")

            # Receive Data Type
            data_type = conn.recv(DATA_TYPE_SIZE)
            data_type = data_type.decode().strip()
            
        except ConnectionResetError:
            # return empty data if connection is closed by client
            return b""
        except Exception:
            print("Error in receiving Headers: ", traceback.format_exc())
            return b""

        if data_type == "File":
            try:
                # Receive Filename length
                filename_size = conn.recv(self.filename_header_size)
                filename_length = int(filename_size.decode("utf-8").strip())
                
                # Receive filename
                filename = b""
                exception_occured = False
                pending_filename_bytes = filename_length
                while len(filename) < filename_length:
                    if pending_filename_bytes < 2048:
                        chunk = conn.recv(pending_filename_bytes)
                    else:
                        chunk = conn.recv(2048)
                        pending_filename_bytes -= 2048

                    if not chunk:
                        print("Client Disconnected")
                        break
                    else:
                        filename += chunk

                filename = filename.decode("utf-8")
                
                # create Downloads Folder if it doesn't exist
                if not self.download_location.is_dir():
                    self.download_location.mkdir()
                # handle duplicate filenames
                filepath = self.download_location / filename
                copy_count = 0
                while filepath.is_file():
                    copy_count += 1
                    filename = f"{filepath.stem}(c{copy_count})"
                    filepath = self.download_location / f"{filename}{filepath.suffix}"

                # Download the file
                with open(file=filepath, mode='ab+') as file:
                    current_data_length = 0
                    while current_data_length < data_length:
                        chunk = conn.recv(2048)

                        if not chunk:
                            print("Client Disconnected")
                            break
                        else:
                            file.write(chunk)
                            current_data_length += len(chunk)
                            downloaded_percent = current_data_length / data_length * 100
                            print("\r", end="")
                            print(f"{downloaded_percent:.0f}% file downloaded", end="")
                print() # Go to next line after 100% file downloaded is displayed

            except Exception:
                print("File Download Error:", traceback.format_exc())
                self.send_data(sender_conn=conn, receiver=None, data='Error Receiving Text')
                exception_occured = True
                
            if not exception_occured:
                self.send_data(sender_conn=conn, receiver=None, data='File Downloaded')
                return b'File Saved'
 
        elif data_type in ('Text', 'POLL'):
            self.print_received_text = True
            data = b""
            current_data_length = 0
            exception_occured = False
            while current_data_length < data_length:
                try:
                    chunk = conn.recv(2048)

                    if not chunk:
                        print("Client Disconnected")
                        break
                    else:
                        data += chunk
                        current_data_length = len(chunk)
                except Exception:
                    print("Text Reading Error: ", traceback.format_exc())
                    self.send_data(sender_conn=conn, receiver=None, data='Error Receiving Text')
                    exception_occured = True
                    break
            if not exception_occured and data_type == 'Text':
                self.send_data(sender_conn=conn, receiver=None, data='Text Received')
            elif not exception_occured and data_type == 'POLL':
                self.print_received_text = False
                return data
    

    def handle_client(self, conn, addr):


        # Validate Username provided by client by checking if it already exists in client_dict
        # If username is unique add it to client_dict
        try:
            while True:
                username = conn.recv(2048).decode('utf-8')
                print(f"Selected Username: {username}")
                if len(self.client_dict) > 0:
                    username = None
                    print('Cannot Connet with client/sender. Server/Receiver is already connected with another device')
                    self.send_data(sender_conn=conn, receiver=None, data='Receiver is already connected with another device')
                    break
                elif not self.client_dict.get(username):
                    self.client_dict.update({username: conn})
                    self.send_data(sender_conn=conn, receiver=None, data=username)
                    break
                else:
                    self.send_data(sender_conn=conn, receiver=None, data='Username already taken')

            print("client_dict: ", self.client_dict)
        except Exception:
            print("Error in setting up client 'Username'")
            print(traceback.format_exc())
            conn.close()
            print(f"Lost Connection with {addr}")
        else:
            while True:
                data = self.receive_data(conn)
                if not data:
                    break
                else:
                    if self.print_received_text:
                        print(f"Data from {username}:", data.decode("utf-8"))
                    # data = f"{username}: ".encode("utf-8") + data
                    # for client_username, receiver_conn in self.client_dict.items():
                    #     if client_username != username and receiver_conn:
                    #         print(f"Sending data to {username}")
                    #         self.send_data(conn, client_username, data)


            # conn.sendall(f"{data_length} bytes received".encode("utf-8"))
            # In case of sender trying to connect to busy receiver, username is set to None
            # and username is not added to client_dict.
            if username:
                self.client_dict.pop(username)
                print("client dict: ", self.client_dict)
            conn.close()
            print(f"Lost Connection with {username if username else addr}")

def start_server():
    s = Server()
    while True:
        try:
            conn, addr = s.server.accept()
            print("Connected to:", addr)
            t = threading.Thread(target=s.handle_client, args=(conn, addr), daemon=True)
            t.start()
        except KeyboardInterrupt as e:
            for usrname in s.client_dict.keys():
                # Sending empty data will force client to close socket from its side
                s.client_dict[usrname].sendall(b"")
                # close socket from server side
                s.client_dict[usrname].close()
            s.client_dict.clear()
            print(s.client_dict)
            s.server.close()
            print("Shutting down the server")
            break
        except Exception as e:
            print('Unexpected Server Error:\n', traceback.format_exc())
            print(s.client_dict)
            s.server.close()
            print("Shutting down the server")
            break


if __name__ == "__main__":
    start_server()