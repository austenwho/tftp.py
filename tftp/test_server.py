import logging
import unittest
import uuid
import socket
import socketserver
import threading

import server
import storage

logging.basicConfig(
    format='%(asctime)s -- %(levelname)s: %(message)s',
    level=logging.DEBUG)

class TestHandlerHelpers(unittest.TestCase):
    """Testing functions that do not need a server to be instantiated"""
    def test_unpackOpcodeValues(self):
        b = bytearray()
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes("my_file", 'utf-8'))
        b.append(0)
        b.extend(bytes("netascii", 'utf-8'))
        b.append(0)

        for i in range(1, 6):
            b[1] = i
            t = server.unpackOpcode(b)
            self.assertEqual(t, i)

    def test_unknownOpcodeException(self):
        b = bytearray()
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes("my_file", 'utf-8'))
        b.append(0)
        b.extend(bytes("netascii", 'utf-8'))
        b.append(0)

        # Test Opcode 0
        self.assertRaises(
            server.ErrorUnknownOpcode,
            server.unpackOpcode,
            b)

        # Test Opcode 6
        b[1] = 6
        self.assertRaises(
            server.ErrorUnknownOpcode,
            server.unpackOpcode,
            b)

    def test_UnknownErrorCodes(self):
        self.assertRaises(
            server.ErrorUnknownErrorCode,
            server.packERROR,
            -1,
            "Cabbage Icecream!"
            )

        self.assertRaises(
            server.ErrorUnknownErrorCode,
            server.packERROR,
            8,
            "Cabbage Icecream!"
            )

    def test_packError(self):
        b = bytearray()
        b.extend(server.Opcodes['ERROR'].to_bytes(2, 'big'))
        b.extend(int(0).to_bytes(2, 'big'))
        b.extend(bytes('Cabbage Icecream!', 'utf-8'))
        b.append(0)

        for i in range(8):
            b[3] = i
            e = server.packERROR(i, 'Cabbage Icecream!')
            self.assertEqual(b, e)

    def test_packDATA_withData(self):
        blockNum = 55
        d = str(uuid.uuid1())
        data = bytes(d, 'utf-8')
        b = bytearray()
        b.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))
        b.extend(data)

        dp = server.packDATA(data, blockNum)
        self.assertEqual(dp, b)

    def test_packDATA_zeroLength(self):
        blockNum = 55
        data = bytearray()
        b = bytearray()
        b.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))
        b.extend(data)

        dp = server.packDATA(data, blockNum)
        self.assertEqual(dp, b)

    def test_unpackDATA_withData(self):
        blockNum = 55
        d = str(uuid.uuid1())
        data = bytearray()
        data.extend(bytes(d, 'utf-8'))
        b = bytearray()
        b.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))
        b.extend(data)

        tOp, tBlock, tData = server.unpackDATA(b)
        self.assertEqual(tOp, server.Opcodes['DATA'])
        self.assertEqual(tBlock, blockNum)
        self.assertEqual(tData, data)

    def test_unpackDATA_malformedPacket(self):
        b = bytearray()
        b.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        b.append(55)

        self.assertRaises(
            server.ErrorMalformedPacket,
            server.unpackDATA,
            b)

    def test_unpackDATA_illegalOperation(self):
        blockNum = 55
        data = "hereissomedata"
        b = bytearray()
        b.extend(server.Opcodes['WRQ'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))
        b.extend(bytes(data, 'utf-8'))

        self.assertRaises(
            server.ErrorIllegalOperation,
            server.unpackDATA,
            b)

    def test_unpackRWRQ_illegalOperation(self):
        filename = 'myfile'
        mode = 'netascii'
        b = bytearray()
        b.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.append(0)
        b.extend(bytes(mode, 'utf-8'))
        b.append(0)

        self.assertRaises(
            server.ErrorIllegalOperation,
            server.unpackRWRQ,
            b)

    def test_unpackRWRQ_missingFilenameTermination(self):
        filename = 'myfile'
        mode = 'netascii'
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.extend(bytes(mode, 'utf-8'))

        self.assertRaises(
            server.ErrorMalformedPacket,
            server.unpackRWRQ,
            b)

    def test_unpackRWRQ_missingModeTermination(self):
        filename = 'myfile'
        mode = 'netascii'
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.append(0)
        b.extend(bytes(mode, 'utf-8'))

        self.assertRaises(
            server.ErrorMalformedPacket,
            server.unpackRWRQ,
            b)

    def test_unpackRWRQ_missingFilename(self):
        filename = ''
        mode = 'netascii'
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.append(0)
        b.extend(bytes(mode, 'utf-8'))
        b.append(0)

        self.assertRaises(
            storage.ErrorEmptyPath,
            server.unpackRWRQ,
            b)

    def test_unpackRWRQ_unknownMode(self):
        filename = 'myfile'
        mode = 'say_friend_and_open'
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.append(0)
        b.extend(bytes(mode, 'utf-8'))
        b.append(0)

        self.assertRaises(
            server.ErrorUnknownMode,
            server.unpackRWRQ,
            b)

    def test_unpackRWRQ(self):
        filename = 'myfile'
        mode = 'octet'
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(filename, 'utf-8'))
        b.append(0)
        b.extend(bytes(mode, 'utf-8'))
        b.append(0)

        tOp, tFile, tMode = server.unpackRWRQ(b)
        self.assertEqual(tOp, server.Opcodes['RRQ'])
        self.assertEqual(tFile, filename)
        self.assertEqual(tMode.lower(), mode)

    def test_unpackACK_illegalOperation(self):
        b = bytearray()
        b.extend(server.Opcodes['ERROR'].to_bytes(2, 'big'))
        b.extend(int(55).to_bytes(2, 'big'))

        self.assertRaises(
            server.ErrorIllegalOperation,
            server.unpackACK,
            b)

    def test_unpackACK(self):
        blockNum = 55
        b = bytearray()
        b.extend(server.Opcodes['ACK'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))

        tOp, tBlock = server.unpackACK(b)
        self.assertEqual(tOp, server.Opcodes['ACK'])
        self.assertEqual(tBlock, blockNum)

    def test_packACK(self):
        blockNum = 55
        b = bytearray()
        b.extend(server.Opcodes['ACK'].to_bytes(2, 'big'))
        b.extend(blockNum.to_bytes(2, 'big'))

        tP = server.packACK(blockNum)
        self.assertEqual(tP, b)

    def test_encodeNetascii(self):
        # UNIX newline \n
        # Macintosh newline \r
        # DOS newline \r\n
        # Inverted DOS newline \n\r
        input = b'\n\r\r\n\n\r'
        output = bytearray(b'\r\n\r\x00\r\x00\r\n\r\n\r\x00')
        test = server.encodeNetascii(input)
        self.assertEqual(test, output)

    def test_decodeNetascii(self):
        # UNIX newline \n
        # Macintosh newline \r
        # DOS newline \r\n
        # Inverted DOS newline \n\r
        output = bytearray(b'\n\r\r\n\n\r')
        input = b'\r\n\r\x00\r\x00\r\n\r\n\r\x00'
        test = server.decodeNetascii(input)
        self.assertEqual(test, output)



class TestServer(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingUDPServer(('localhost',0), server.Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.send_to = self.server.server_address
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_thread.start()

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()

    def test_handleRRQ(self):
        store = storage.Storage()
        d = str(uuid.uuid1())
        # Guarantee file is at least 2 data packets long
        d = (d * 512)[:1024]
        file = bytearray()
        file.extend(bytes(d, 'utf-8'))
        fileName = 'my_file'
        store.put(fileName, file)

        # Build and send RRQ packet
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(fileName, 'utf-8'))
        b.append(0)
        b.extend(bytes('netascii', 'utf-8'))
        b.append(0)
        self.client.sendto(b, self.send_to)

        # Get data block #1
        answer1, self.send_to = self.client.recvfrom(1024)

        # Build ACK packet for data block #1
        a = bytearray()
        a.extend(int(4).to_bytes(2, 'big'))
        a.extend(int(1).to_bytes(2, 'big'))
        self.client.sendto(a, self.send_to)

        # Get data block #2
        answer2, self.send_to = self.client.recvfrom(1024)

        # Build and send ACK for data block #2
        a[3] = 2
        self.client.sendto(a, self.send_to)

        # Get data block #3
        answer3, self.send_to = self.client.recvfrom(1024)

        # Build and send ACK for data block #3
        a[3] = 3
        self.client.sendto(a, self.send_to)

        self.assertEqual(answer1[4:], file[0:512])
        self.assertEqual(answer2[4:], file[512:1024])
        self.assertEqual(answer3[4:], file[1024:])

    def test_handleWRQ(self):
        store = storage.Storage()
        fileName = 'writing_file'

        d = str(uuid.uuid1())
        # Guarantee file is at least 2 data packets long
        d = (d * 512)[:1024]

        # file is netascii encoded for transmission
        file = bytearray()
        file.extend(bytes(d, 'utf-8'))
        file.extend(b'\r\n\r\x00\r\x00\r\n\r\n\r\x00')

        # file2 is netascii decoded
        file2 = bytearray()
        file2.extend(bytes(d, 'utf-8'))
        file2.extend(b'\n\r\r\n\n\r')

        # Build and send RRQ packet
        b = bytearray()
        b.extend(server.Opcodes['WRQ'].to_bytes(2, 'big'))
        b.extend(bytes(fileName, 'utf-8'))
        b.append(0)
        b.extend(bytes('netascii', 'utf-8'))
        b.append(0)
        self.client.sendto(b, self.send_to)

        # Get ACK block #0
        answer1, self.send_to = self.client.recvfrom(1024)

        # Build DATA packet for data block #1
        dataBlock = 1
        a = bytearray()
        a.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        a.extend(dataBlock.to_bytes(2, 'big'))
        a.extend(file[0:512])
        self.client.sendto(a, self.send_to)

        # Get ACK block #1
        answer2, self.send_to = self.client.recvfrom(1024)

        # Build and send DATA for data block #2
        dataBlock += 1
        a2 = bytearray()
        a2.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        a2.extend(dataBlock.to_bytes(2, 'big'))
        a2.extend(file[512:1024])
        self.client.sendto(a2, self.send_to)

        # Get data block #2
        answer3, self.send_to = self.client.recvfrom(1024)

        # Build and send DATA for data block #3
        dataBlock += 1
        a3 = bytearray()
        a3.extend(server.Opcodes['DATA'].to_bytes(2, 'big'))
        a3.extend(dataBlock.to_bytes(2, 'big'))
        a3.extend(file[1024:])
        self.client.sendto(a3, self.send_to)

        answer4, self.send_to = self.client.recvfrom(1024)

        self.assertEqual(int.from_bytes(answer1[2:], 'big'), 0)
        self.assertEqual(int.from_bytes(answer2[2:], 'big'), 1)
        self.assertEqual(int.from_bytes(answer3[2:], 'big'), 2)
        self.assertEqual(int.from_bytes(answer4[2:], 'big'), 3)

        self.client.close()
        self.send_to = self.server.server_address
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b = bytearray()
        b.extend(server.Opcodes['RRQ'].to_bytes(2, 'big'))
        b.extend(bytes(fileName, 'utf-8'))
        b.append(0)
        b.extend(bytes('octet', 'utf-8'))
        b.append(0)

        self.client.sendto(b, self.send_to)
        d1, self.send_to = self.client.recvfrom(1024)

        ak = bytearray()
        ak.extend(server.Opcodes['ACK'].to_bytes(2, 'big'))
        ak.extend(int(1).to_bytes(2, 'big'))

        self.client.sendto(ak, self.send_to)
        d2, self.send_to = self.client.recvfrom(1024)

        ak[3] = 2
        self.client.sendto(ak, self.send_to)

        d3, self.send_to = self.client.recvfrom(1024)

        ak[3] = 3
        self.client.sendto(ak, self.send_to)

        data = bytearray()
        op, block, d = server.unpackDATA(d1)
        data.extend(d)
        op, block, d = server.unpackDATA(d2)
        data.extend(d)
        op, block, d = server.unpackDATA(d3)
        data.extend(d)

        self.assertEqual(data, file2)

if __name__ == '__main__':
    unittest.main()
