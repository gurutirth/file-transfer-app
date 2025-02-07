import re
import socket
import threading
import traceback
import time
import pathlib

DATA_TYPE_SIZE = 10

class Client():

    def __init__(self, server_ip=None, port=5555, data_header_size=13, filename_header_size=7):
        """
        Initialize the Network object with server and port details.
        Creates a socket and establishes a connection to the server.

        :param server: The IP address of the server.
        :param port: The port number to connect to.
        """

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_ip = server_ip
        self.port = port
        self.data_header_size = data_header_size
        self.filename_header_size = filename_header_size
        self.addr = (self.server_ip, self.port)
        self.id = self.connect()
        if self.id:
            self.client_closed = False
            print("Connected to Server as", self.id, "\n")
        else:
            self.client_closed = True

    def set_username(self):
        """Set a unique username"""
        
        while True:
            username = input("Select your username (max 20 alpha-numeric characters): ")
            username_regex = r'[a-zA-Z0-9]{1,20}'
            if not re.fullmatch(username_regex, username):
                print('Invalid Username. Try Again.')
                continue
            self.client.send(username.encode('utf-8'))
            username_status = self._receive_data().decode('utf-8')
            if username_status == 'Receiver is already connected with another device':
                print(username_status)
                return
            elif username_status == "Username already taken":
                print(username_status)
                continue
            else:
                break
        return username


    def connect(self):
        """
        Connect to the server and receive an initial response.

        :return: Decoded server response or None if connection fails.
        """

        try:
            self.client.connect(self.addr)
            username = self.set_username()
            return username
            # return self.client.recv(2048).decode()
        except Exception as e:
            print("Connection Error: ", e)
            raise


    def poll_server(self):
        """Continuously polls the server for updates."""
        
        while True:
            try:
                # send a poll request to server
                self.send_text("POLL", data_type='POLL')
                data = self._receive_data()
                if data:
                    print(f'{data.decode("utf-8"):<20}')
                    # print(f"\n{self.id}: ", end="")
                    print("\nEnter File Path: ", end="")
                else:
                    self.client_closed = True
                    self.close()
                    print("Press Enter to close the client Application")
                    break
                time.sleep(1)  # Optional delay between polls
            except ConnectionResetError:
                print("Connection closed by server.")
                break
            except Exception as e:
                print("Polling Error: ", e)
                break


    def send_text(self, data: str, data_type: str):
        """
        Send text data to the server.

        :param data: The data to send to the server.
        :return: "Data Sent" in case of success and None in case of failure.
        """

        try:
            encoded_data = data.encode("utf-8")
            data_length = len(encoded_data)

            # Send the length of data as a <data_header_size>-byte header
            header = f"{data_length:<{(self.data_header_size)}}".encode("utf-8")
            self.client.sendall(header)

            # Send Data Type in next <DATA_TYPE_SIZE> bytes
            self.client.sendall(f"{data_type:<{(DATA_TYPE_SIZE)}}".encode("utf-8"))

            # Send the actual data
            self.client.sendall(encoded_data)

            # return self._receive_data()
            return "Data Sent"
        except socket.error as e:
            print("Text Sending Socket Error:", traceback.format_exc())
        except Exception:
            print("Text Sending General Error:", traceback.format_exc())
            

    def send_file(self, filepath: str):
        """
        Send file data to the server.

        :param data: The data to send to the server.
        :return: "Data Sent" in case of success and None in case of failure.
        """

        try:
            with open(file=pathlib.Path(filepath.strip()), mode='rb+') as file:
                file_size = file.seek(0, 2)
                file.seek(0)

                data_length = file_size

                # Send the length of data as a <data_header_size>-byte header
                data_header = f"{data_length:<{(self.data_header_size)}}".encode("utf-8")
                self.client.sendall(data_header)

                # Send Data Type in next <DATA_TYPE_SIZE> bytes
                self.client.sendall(f"{'File':<{(DATA_TYPE_SIZE)}}".encode("utf-8"))

                # Send File Name
                filepath = pathlib.Path(filepath)
                filename = filepath.name
                encoded_filename = filename.encode("utf-8")
                filename_length = len(encoded_filename)

                ## Send length of File Name as <filename_header_size>-byte header
                filename_header = f"{filename_length:<{(self.filename_header_size)}}".encode("utf-8")
                self.client.sendall(filename_header)

                ## Send File Name
                self.client.sendall(encoded_filename)

                # Send the actual file data
                current_data_length = 0
                while True:
                    chunk = file.read(2048)
                    self.client.send(chunk)
                    if not chunk:
                        break

                    current_data_length += len(chunk)
                    print('\r', end="")
                    print(f'{current_data_length / data_length * 100:.0f}% file sent', end="")
                print() # blank line

                # return self._receive_data()
                return "Data Sent"
        except socket.error as e:
            print("File Sending Socket Error:", traceback.format_exc())
        except Exception as e:
            print("File Sending General Error:", traceback.format_exc())

    def send_data(self, data, data_type):
        if data_type == 'Text':
            self.send_text(data=data, data_type='Text')
        elif data_type == 'POLL':
            self.send_text(data=data, data_type='POLL')
        elif data_type == 'File':
            self.send_file(data)


    def _receive_data(self):
        """
        Receive data from the server in a loop to handle large responses.

        :return: The complete decoded server response.
        """

        try:
            data_header = self.client.recv(self.data_header_size)
            if not data_header:
                print("Server Disconnected")
                return b""

            data_length = int(data_header.decode("utf-8").strip())
            # print(f'Expecting {data_length} bytes of data')
            print('\r', end="")

            data = b""
            while len(data) < data_length:
                try:
                    chunk = self.client.recv(2048)
                    if not chunk:
                        print('Disconnected from server')
                        break
                    else:
                        data += chunk

                except Exception as e:
                    print("Data reading error: ", traceback.format_exc())
                    break

            return data
        except socket.error as e:
            print("Receive Error: ", e)
            return
        except Exception as e:
            print("Data Reading General error: ", e)
            return


    def close(self):
        """
        Close the client socket connection.
        """
        try:
            self.client.close()
            print("Connection closed from client side.")
        except socket.error as e:
            print(f"Error while closing the connection: {e}")
            raise


def start_client():

    # Get Server details to connect with it
    try:
        ipv4_regex = r"^((25[0-5]|2[0-4]\d|1\d\d|\d\d?)\.){3}(25[0-5]|2[0-4]\d|1\d\d|\d\d?)$"
        server_ip = input("Enter receiver ip address: ").strip()
        if not re.search(ipv4_regex, server_ip):
            raise ValueError("Invalid IPV4 Address entered")
        server_port = int(input("Enter port number: "))
    except ValueError as e:
        print(traceback.format_exc())
        return

    # Connect with client and listen for data in a separate tread
    try:
        n = Client(server_ip=server_ip, port=server_port)
        if not n.client_closed:
            t = threading.Thread(target=n.poll_server, daemon=True)
            t.start()
        else:
            t = None
            n.close()
    except KeyboardInterrupt:
        print("Exiting server without setting username")
    except Exception:
        print("Error while setting up client:", traceback.format_exc())
    else:
        # If connection is successfully established, set up while loop to send Data contineously
        while t and t.is_alive():
            try:
                # msg = input(f"{n.id}: ")
                msg = input("Enter File Path: ").strip()
                if msg:
                    response = n.send_data(data=msg, data_type='File')
                else:
                    continue
                # if response:
                #     print(f"Server Response: {response}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(traceback.format_exc())
                break
        print("Closing Client Application")
        if not n.client_closed:
            n.close()


if __name__ == '__main__':
    start_client()