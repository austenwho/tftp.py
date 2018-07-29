import threading

class EmptyPathException(Exception):
    pass

class FileNotFoundException(Exception):
    pass

class FileExistsException(Exception):
    pass

class Storage(object):
    """Storage is a singleton thread-safe memory file store"""
    __instance = None

    def __new__(cls):
        if not Storage.__instance:
            Storage.__instance = Storage.__Storage()
        return Storage.__instance

    class __Storage():
        def __init__(self):
            self.mutex = threading.Lock()
            self.store = {}

        def get(self, path=None):
            if not path:
                raise EmptyPathException("Must supply a file path!")
            with self.mutex:
                if path in self.store:
                    return self.store[path]
                else:
                    raise FileNotFoundException("No such file '{}'".format(path))

        def put(self, path=None, file=None):
            if not path:
                raise EmptyPathException("Must supply a file path!")
            with self.mutex:
                if path in self.store:
                    raise FileExistsException("File '{}' already exists!".format(path))
                else:
                    self.store[path] = file
