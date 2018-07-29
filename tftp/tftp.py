import logging
import socket
import socketserver
import tftp.server

logging.basicConfig(format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.INFO)

HOST = 'localhost'
PORT = 69

def main():
    print("Hello, I'm about to be a TFTP server!")

if __name__ == '__main__':
    main()
