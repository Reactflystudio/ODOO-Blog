import socket
import sys

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.settimeout(2)
            s.connect((host, port))
            return True
        except:
            return False

if __name__ == "__main__":
    if check_port("127.0.0.1", 8000):
        print("ONLINE")
    else:
        print("OFFLINE")
