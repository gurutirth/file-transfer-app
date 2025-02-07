from server import start_server
from client import start_client

while True:

    action = input("What do you want to do (send/receive)? ")

    if action.strip().casefold() == "receive":
        print()
        start_server()
        break
    elif action.strip().casefold() == "send":
        print()
        start_client()
        break
    else:
        print("Invalid input. Input can only be 'send' or 'receive'.")
