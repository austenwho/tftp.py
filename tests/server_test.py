import unittest
import context
import threading
import socket
import tftp.server as server

class TestHandlerHelpers(unittest.TestCase):
    """Testing functions that do not need a server to be instantiated"""
    def test_parseOpcodeValues(self):
        b = bytearray()
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes("my_file", 'ascii'))
        b.append(0)
        b.extend(bytes("netascii", 'ascii'))
        b.append(0)

        for i in range(1, 6):
            b[1] = i
            t = server.unpackOpcode(b)
            self.assertEqual(t, i)

    def test_unknownOpcodeException(self):
        b = bytearray()
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes("my_file", 'ascii'))
        b.append(0)
        b.extend(bytes("netascii", 'ascii'))
        b.append(0)

        # Test Opcode 0
        self.assertRaises(
            server.UnknownOpcodeException,
            server.unpackOpcode,
            b)

        # Test Opcode 6
        b[1] = 6
        self.assertRaises(
            server.UnknownOpcodeException,
            server.unpackOpcode,
            b)

    def test_UnknownErrorCodes(self):
        self.assertRaises(
            server.UnknownErrorCodeException,
            server.packERROR,
            -1,
            "Cabbage Icecream!"
            )

        self.assertRaises(
            server.UnknownErrorCodeException,
            server.packERROR,
            8,
            "Cabbage Icecream!"
            )

    def test_buildError(self):
        b = bytearray()
        b.extend(server.Opcodes['ERROR'].to_bytes(2, 'big'))
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes('Cabbage Icecream!', 'ascii'))
        b.append(0)

        for i in range(8):
            b[3] = i
            e = server.packERROR(i, 'Cabbage Icecream!')
            self.assertEqual(b, e)

class TestServer(unittest.TestCase):
    def setUp(self):
        self.server = server.Server(('localhost',0), server.Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.send_to = self.server.server_address
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_thread.start()

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()

    def test_handleRRQ(self):
        b = bytearray()
        b.extend(int(1).to_bytes(2, 'big'))
        b.extend(bytes('my_file', 'ascii'))
        b.append(0)
        b.extend(bytes('netascii', 'ascii'))
        b.append(0)

        self.client.sendto(b, self.send_to)
        answer = self.client.recv(1024)
        print("\n{}\n".format(answer))

if __name__ == '__main__':
    unittest.main()
