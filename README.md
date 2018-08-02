# tftp.py
Python implementation of [RFC-1350](https://tools.ietf.org/html/rfc1350): TFTP

## Usage

tftp.py defaults to port 20069 instead of 69 so privileged access is not requred. The current implementation of tftp.py only supports octet data transfer mode.

To run:

```
python3 tftp/tftp.py
```

To test, use a standard TFTP client:

```
tftp 127.0.0.1 20069
tftp> binary
tftp> verbose
tftp> trace
tftp> put <some_localfile> <some_remotefile>
tftp> get <some_remotefile>
```

## ToDo:
- Implement NETASCII encode/deocde to complete the spec
- Allow command-line setting of logging level
