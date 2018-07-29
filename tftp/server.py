import logging
import socket
import socketserver
import tftp.storage as storage
import threading

logging.basicConfig(format='%(asctime)s -- %(levelname)s: %(message)s', level=logging.DEBUG)

SOCKET_TIMEOUT = 5.0
MAX_BLOCK_SEND_ATTEMPTS = 10

class ErrorUnknownOpcode(Exception):
    pass

class ErrorUnknownErrorCode(Exception):
    pass

class ErrorIllegalOperation(Exception):
    pass

class ErrorUnknownMode(Exception):
    pass

class ErrorMalformedPacket(Exception):
    pass

Opcodes = {
    'RRQ': 0x01,
    'WRQ': 0x02,
    'DATA': 0x03,
    'ACK': 0x04,
    'ERROR': 0x05,
    0x01: 'RRQ',
    0x02: 'WRQ',
    0x03: 'DATA',
    0x04: 'ACK',
    0x05: 'ERROR'}

Errors = {
    'NOT_DEFINED': 0x00,
    'FILE_NOT_FOUND': 0x01,
    'ACCESS_VIOLATION': 0x02,
    'ALLOCATION_EXCEEDED': 0x03,
    'ILLEGAL_OPERATION': 0x04,
    'UNKNOWN_TRANSFER_ID': 0x05,
    'FILE_EXISTS': 0x06,
    'NO_SUCH_USER': 0x07,
    0x00: 'NOT_DEFINED',
    0x01: 'FILE_NOT_FOUND',
    0x02: 'ACCESS_VIOLATION',
    0x03: 'ALLOCATION_EXCEEDED',
    0x04: 'ILLEGAL_OPERATION',
    0x05: 'UNKNOWN_TRANSFER_ID',
    0x06: 'FILE_EXISTS',
    0x07: 'NO_SUCH_USER'}

Modes = {
    'OCTET': 'octet',
    'NETASCII': 'netascii',
    'MAIL': 'mail'}

def unpackOpcode(packet):
    """Returns an integer corresponding to Opcode encoded in packet.

    Raises ErrorUnknownOpcode if Opcode is out of bounds.
    """
    c = int.from_bytes(packet[:2], byteorder='big')
    if c not in Opcodes:
        raise ErrorUnknownOpcode("Unknown Opcode '{}'".format(c))
    return c

def packERROR(code, msg):
    """Returns a byte-ordered TFTP Error packet based on code and msg.

    Raises ErrorUnknownErrorCode when code is out of bounds.
    """
    if code not in Errors:
        raise ErrorUnknownErrorCode("Unknown error code '{}'".format(code))

    b = bytearray()
    b.extend(Opcodes['ERROR'].to_bytes(2, 'big'))
    b.extend(code.to_bytes(2, 'big'))
    b.extend(bytes(msg, 'ascii'))
    b.append(0)
    return b

def packDATA(data, blockNum):
    """Returns byte-formatted DATA packet"""
    b = bytearray()
    b.extend(Opcodes['DATA'].to_bytes(2, 'big'))
    b.extend(blockNum.to_bytes(2, 'big'))
    b.extend(bytes(data, 'utf-8'))
    return b

def unpackDATA(packet):
    """Returns tuple of (Opcode, BlockNum, Data)"""
    opcode = unpackOpcode(packet)
    if opcode != Opcodes['DATA']:
        raise ErrorIllegalOperation(
            "Expected DATA packet, but got '{0}'"\
            .format(Opcodes[opcode]))

    blockNum = int.from_bytes(packet[2:4], 'big')
    data = packet[4:]
    return (opcode, blockNum, data)

def unpackRWRQ(packet):
    """Returns a tuple of (Opcode, Filename, Mode)"""
    opcode = unpackOpcode(packet)
    if opcode not in (Opcodes['RRQ'], Opcodes['WRQ']):
        raise ErrorIllegalOperation(
            "Expected RRQ or WRQ but got '{0}'"\
            .format(Opcodes[opcode]))

    s = 2
    e = packet.find(0, s)
    if e < s:
        raise ErrorMalformedPacket("Couldn't find filename termination byte")
    filename = packet[s:e].decode('utf-8')

    s = e + 1
    e = packet.find(0, s)
    if e < s:
        raise ErrorMalformedPacket("Couldn't find mode termination byte")
    mode = packet[s:e].decode('utf-8')

    if not filename:
        raise storage.EmptyPathException("Filename cannot be empty")
    elif mode.upper() not in Modes:
        raise ErrorUnknownMode(
            "Mode '{}' not recognized"\
            .format(mode))
    return (opcode, filename, mode.upper())

def unpackACK(packet):
    """Returns a tuple of (Opcode, BlockNum)"""
    opcode = unpackOpcode(packet)
    if opcode != Opcodes['ACK']:
        raise ErrorIllegalOperation(
            "Expected ACK packet, but got '{0}'"\
            .format(Opcodes[opcode]))

    blockNum = int.from_bytes(packet[2:4], 'big')
    return (opcode, blockNum)

def packACK(blockNum):
    """Returns a byte-formatted ACK packet"""
    b = bytearray()
    b.extend(Opcode['ACK'].to_bytes(2, 'big'))
    b.extend(blockNum.to_bytes(2, 'big'))
    return b

def sendError(address, sock, err):
    sock.sendto(err, address)

def logClientError(address, error):
    logging.info(
        "Sent error to Client [{0}:{1}]: {2}"\
        .format(address[0], address[1], error))

def sendData(address, sock, data):
    sock.sendto(data, address)

def handleRRQ(address, sock, filename, mode):
    logging.info(
        "Client [{0}:{1}] requested to read file [{2}] using transfer mode [{3}]"\
        .format(*address, filename, mode))
    store = storage.Storage()

    try:
        file = store.get(filename)
    except (storage.ErrorFileNotFound, storage.ErrorEmptyPath) as ex:
        err = packERROR(
            Errors['FILE_NOT_FOUND'],
            str(ex))
        sendError(address, sock, err)
        logClientError(address, err)
        return

    data = None
    sendDATA = False
    readACK = False
    dataBlock = 0
    ackBlock = 0
    fileSize = len(file)
    sendCount = 0
    # s and e are initially incremented by 512 to give data[0:512] slice
    s = -512
    e = 0

    # Control is returned to handler() by explicit return
    while True:
        # Ready for new DATA packet
        if ackBlock == dataBlock:
            dataBlock += 1
            s += 512
            e += 512
            if e > fileSize:
                e = -1

            data = packDATA(file[s:e], dataBlock)
            sendDATA = True
            logging.debug(
                "Client [{0}:{1}]: Creating datablock [{2}] on file {3}[{4}:{5}]"\
                .format(*address, dataBlock, filename, s, e))

        if sendCount >= MAX_BLOCK_SEND_ATTEMPTS:
            err = packERROR(
                Errors['ACCESS_VIOLATION'],
                "Maximum number of block send attempts reached: [{}]"\
                .format(sendCount))
            sendError(address, sock, err)
            logClientError(
                address,
                "Maximum number of block send attempts reached: [{}]"\
                .format(sendCount))
            return

        # We're sending a DATA packet
        if sendDATA:
            try:
                logging.debug(
                    "Client [{0}:{1}]: Sending datablock [{2}]"\
                    .format(*address, dataBlock))
                sendData(address, sock, data)
                sendDATA = False
                readACK = True
                sendCount += 1
            # Assume that a send timeout is a closed connection
            except socket.timeout as ex:
                # Try at least to alert the client before closing connection
                err = packERROR(
                    Errors['NOT_DEFINED'],
                    str(ex))
                sendError(address, sock, err)
                logClientError(address, ex)
                return

        # We're waiting for an ACK packet
        if readACK:
            try:
                logging.debug(
                    "Client [{0}:{1}]: Reading socket for ACK for datablock [{2}]"\
                    .format(*address, dataBlock))
                packet = sock.recv(1024)
                try:
                    opcode, block = unpackACK(packet)
                    # Ignore all ACKs other than for current block
                    if block == dataBlock:
                        ackBlock = block
                        readACK = False
                        sendCount = 0
                        logging.debug(
                            "Client [{0}:{1}]: Received ACK for datablock [{2}]"\
                            .format(*address, block))
                    else:
                        logging.debug(
                            "Client [{0}:{1}]: Received ACK [{2}] for datablock [{3}]"\
                            + " Still waiting for ACK [{2}]"\
                            .format(*address, block, dataBlock))
                except ErrorIllegalOperation as ex:
                    err = packERROR(
                        Errors['ILLEGAL_OPERATION'],
                        str(ex))
                    sendError(address, sock, err)
                    logClientError(address, ex)
                    return
            # If we've timed out waiting for ACK, resend DATA
            except socket.timeout:
                readACK = False
                sendDATA = True
                logging.debug(
                    "Client [{0}:{1}]: Timed out waiting for ACK [{2}]. Resending data."\
                    .format(*address, dataBlock))

        # If we've acked the last block and no more data, we're done!
        if ackBlock == dataBlock and e == -1:
            logging.debug(
                "Client [{0}:{1}]: Finished sending file {2}"\
                .format(*address, filename))
            sock.close()
            return


def handleWRQ(address, sock, filename, mode):
    sock.sendto(
        filename,
        address)

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        packet, sock = self.request
        #sock.settimeout(SOCKET_TIMEOUT)

        try:
            opcode, filename, mode = unpackRWRQ(packet)
        except ErrorUnknownMode as ex:
            err = packERROR(
                Errors['ACCESS_VIOLATION'],
                str(ex))
            sendError(self.client_address, sock, err)
            logClientError(self.client_address, err)
            return
        except storage.ErrorEmptyPath as ex:
            err = packERROR(
                Errors['FILE_NOT_FOUND'],
                str(ex))
            sendError(self.client_address, sock, err)
            logClientError(self.client_address, err)
            return
        except (ErrorIllegalOperation, ErrorUnknownOpcode) as ex:
            err = packERROR(
                Errors['ILLEGAL_OPERATION'],
                str(ex))
            sendError(self.client_address, sock, err)
            logClientError(self.client_address, err)
            return

        if opcode == Opcodes['RRQ']:
            handleRRQ(self.client_address, sock, filename, mode)
        else:
            handleWRQ(self.client_address, sock, filename, mode)

class Server(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass
