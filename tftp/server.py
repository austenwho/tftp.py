import logging
import socketserver
import storage

DATA_BLOCK_SIZE = 512
MAX_PACKET_SEND_ATTEMPTS = 10

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
    'octet': 'OCTET',
    'netascii': 'NETASCII'}

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
    b.extend(bytes(msg, 'utf-8'))
    b.append(0)
    return b

def packDATA(data, blockNum):
    """Returns byte-formatted DATA packet"""
    b = bytearray()
    b.extend(Opcodes['DATA'].to_bytes(2, 'big'))
    b.extend(blockNum.to_bytes(2, 'big'))
    if data:
        b.extend(data)
    return b

def unpackDATA(packet):
    """Returns tuple of (Opcode, BlockNum, Data)"""
    opcode = unpackOpcode(packet)
    if opcode != Opcodes['DATA']:
        raise ErrorIllegalOperation(
            "Expected DATA packet, but got '{0}'"\
            .format(Opcodes[opcode]))

    if len(packet) < 4:
        raise ErrorMalformedPacket("Data packet missing block number")

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
        raise storage.ErrorEmptyPath("Filename cannot be empty")
    elif mode.upper() not in Modes:
        raise ErrorUnknownMode(
            "Mode '{}' not recognized"\
            .format(mode))
    return (opcode, filename, mode.lower())

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
    b.extend(Opcodes['ACK'].to_bytes(2, 'big'))
    b.extend(blockNum.to_bytes(2, 'big'))
    return b

def logClientError(address, error):
    """logClientError takes an address tuple of (address, port)
    and an error message, formats a logline when an error message
    is handled and delivered to the client.
    """
    logging.info(
        "Sent error to Client [{0}:{1}]: {2}"\
        .format(address[0], address[1], error))

def encodeNetascii(data):
    """TFTP adopts the modifications to US-ASCII from RFC-764 Telnet
    specification for transmission of newline characters. All LF
    characters are converted into CR LF sequences, and all CR characters
    are encoded into CR NULL sequences.

    Example:
    >>> First\nSecond\r\nThird\rFourth\n\r
    would become:
    >>> First\r\nSecond\r\x00\r\nThird\r\x00Fourth\r\n\r\x00
    """
    CR = 0x0D
    LF = 0x0A
    out = bytearray()
    for b in data:
        if b == LF:
            out.append(CR)
            out.append(LF)
        elif b == CR:
            out.append(CR)
            out.append(0)
        else:
            out.append(b)
    return out

def decodeNetascii(data):
    """*See encodeNetascii"""
    CR = 0x0D
    LF = 0x0A
    NULL = 0x00
    skip = False
    lenData = len(data)
    next = None
    out = bytearray()
    for i, b in enumerate(data):
        next = None if i+1 >= lenData else data[i+1]
        if skip:
            skip = False
            continue
        if b == CR and next == LF:
            out.append(LF)
            skip = True
        elif b == CR and next == NULL:
            out.append(CR)
            skip = True
        else:
            out.append(b)
    return out

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
        sock.sendto(err, address)
        logClientError(address, ex)
        return

    if mode == Modes['NETASCII']:
        file = encodeNetascii(file)

    data = None
    sendDATA = False
    readACK = False
    dataBlock = 0
    ackBlock = 0
    fileSize = len(file)
    sendCount = 0
    # start and end are initially incremented by 512 to give file[0:512] slice
    start = -512
    end = 0

    # Control is returned to handler() by explicit return
    while True:
        # Ready to build a new DATA packet
        if ackBlock == dataBlock:
            dataBlock += 1
            start += 512
            end += 512
            if end > fileSize:
                end = None

            data = packDATA(file[start:end], dataBlock)
            sendDATA = True
            logging.debug(
                "Client [{0}:{1}]: Creating datablock [{2}] on file {3}[{4}:{5}]"\
                .format(*address, dataBlock, filename, start, end))

        # Don't loop forever trying to send the same data packet
        if sendCount >= MAX_PACKET_SEND_ATTEMPTS:
            err = packERROR(
                Errors['ACCESS_VIOLATION'],
                "Maximum number of packet send attempts reached: [{}]"\
                .format(sendCount))
            sock.sendto(err, address)
            logClientError(
                address,
                "Maximum number of packet send attempts reached: [{}]"\
                .format(sendCount))
            return

        # We're sending a DATA packet
        if sendDATA:
            logging.debug(
                "Client [{0}:{1}]: Sending datablock [{2}]"\
                .format(*address, dataBlock))
            sock.sendto(data, address)
            sendDATA = False
            readACK = True
            sendCount += 1

        # We're waiting for an ACK packet
        if readACK:
            logging.debug(
                "Client [{0}:{1}]: Waiting for ACK for datablock [{2}]"\
                .format(*address, dataBlock))
            packet = sock.recv(1024)
            if not packet:
                # If we've timed out waiting for ACK, resend DATA
                readACK = False
                sendDATA = True
                logging.debug(
                    "Client [{0}:{1}]: Timed out waiting for ACK [{2}]. Resending data."\
                    .format(*address, dataBlock))
            else:
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
                    sock.sendto(err, address)
                    logClientError(address, ex)
                    return

        # If we've acked the last block and no more data, we're done!
        if ackBlock == dataBlock and end == None:
            logging.debug(
                "Client [{0}:{1}]: Finished sending file {2}"\
                .format(*address, filename))
            return


def handleWRQ(address, sock, filename, mode):
    """Acknowleges WRQ request by sending ACK[0] packet to client.
    Reads DATA from sock until len(DATA) < 512.
    ACKs each DATA packet with DATA's block number.
    """
    logging.info(
        "Client [{0}:{1}] requested to put file [{2}] using transfer mode [{3}]"\
        .format(*address, filename, mode))
    store = storage.Storage()

    if filename in store.store:
        err = packERROR(
            Errors['FILE_EXISTS'],
            "File '{}' already exists".format(filename))
        sock.sendto(err, address)
        logClientError(
            address,
            "File '{}' already exists".format(filename))
        return

    file = bytearray()
    ackBlock = -1
    dataBlock = 0
    sendCount = 0
    sendACK = False
    readDATA = False
    terminateTransfer = False

    while True:
        # Build a new ACK packet to acknowledge received DATA packet
        if ackBlock != dataBlock:
            logging.debug(
                "Client [{0}:{1}]: Updating ACK [{2}] to ACK [{3}]"\
                .format(*address, ackBlock, dataBlock))
            ackBlock += 1
            ack = packACK(ackBlock)
            sendACK = True

        # Send ACK
        if sendACK:
            try:
                logging.debug(
                    "Client [{0}:{1}]: Sending ACK [{2}]"\
                    .format(*address, ackBlock))
                sock.sendto(ack, address)
                sendCount += 1
                sendACK = False
                readDATA = True
            except ex:
                logging.error("Socket send error during WRQ sendACK: {}".format(ex))
                return

            # File transfer is terminated by acknowledging the last data packet
            if terminateTransfer:
                logging.debug(
                    "Client [{0}:{1}]: Terminating transfer. Writing [{2}] bytes of '{3}'"\
                    .format(*address, len(file), filename))

                if mode == Modes['NETASCII']:
                    file = decodeNetascii(file)

                store.put(filename, file)
                return

        # Don't try and send ACK packets for ever...
        if sendCount >= MAX_PACKET_SEND_ATTEMPTS:
            err = packERROR(
                Errors['ACCESS_VIOLATION'],
                "Maximum number of packet send attempts reached: [{}]"\
                .format(sendCount))
            try:
                sock.sendto(err, address)
                logClientError(
                    address,
                    "Maximum number of packet send attempts reached: [{}]"\
                    .format(sendCount))
            except Exception as ex:
                logging.error(
                    "Socket send error during WRQ sendCount: {}"\
                    .format(ex))
            return

        # Read DATA
        if readDATA:
            packet = sock.recv(1024)
            if packet:
                try:
                    opcode, block, chunk = unpackDATA(packet)
                except (ErrorMalformedPacket, ErrorIllegalOperation) as ex:
                    err = packERROR(
                        Errors['ILLEGAL_OPERATION'],
                        str(ex))
                    sock.sendto(err, address)
                    logClientError(address, ex)
                    return

                if block == dataBlock + 1:
                    logging.debug(
                        "Client [{0}:{1}]: Reading DATA [{2}]"\
                        .format(*address, block))
                    sendCount = 0
                    dataBlock = block
                    # Chunk could be zero-length if last packet
                    if chunk:
                        file.extend(chunk)

                    if len(chunk) < DATA_BLOCK_SIZE:
                        terminateTransfer = True
                else:
                    logging.debug(
                        "Client [{0}:{1}]: Received duplicate DATA [{2}] Still waiting for DATA [{3}]"\
                        .format(*address, block, dataBlock + 1))

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        packet, sock = self.request
        logging.debug("Receiving packet from client: {}".format(packet))
        
        try:
            opcode, filename, mode = unpackRWRQ(packet)
        except ErrorUnknownMode as ex:
            err = packERROR(
                Errors['ACCESS_VIOLATION'],
                str(ex))
            sock.sendto(err, self.client_address)
            logClientError(self.client_address, err)
            return
        except storage.ErrorEmptyPath as ex:
            err = packERROR(
                Errors['FILE_NOT_FOUND'],
                str(ex))
            sock.sendto(err, self.client_address)
            logClientError(self.client_address, err)
            return
        except (ErrorIllegalOperation, ErrorUnknownOpcode) as ex:
            err = packERROR(
                Errors['ILLEGAL_OPERATION'],
                str(ex))
            sock.sendto(err, self.client_address)
            logClientError(self.client_address, err)
            return

        if opcode == Opcodes['RRQ']:
            handleRRQ(self.client_address, sock, filename, mode)
        else:
            handleWRQ(self.client_address, sock, filename, mode)
