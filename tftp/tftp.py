import logging
import socketserver
import server
import threading

logging.basicConfig(
    format='%(asctime)s -- %(levelname)s: %(message)s',
    level=logging.DEBUG)

HOST = 'localhost'
PORT = 20069

if __name__ == '__main__':
    logging.info("Starting TFTP server on {0}:{1}".format(HOST, PORT))
    srv = socketserver.UDPServer((HOST, PORT), server.Handler)
    thread = threading.Thread(target=srv.serve_forever)
    thread.start()
