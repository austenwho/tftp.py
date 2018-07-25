import threading

class EmptyPathException(Exception):
    pass

class FileNotFoundException(Exception):
    pass

class Storage(object):
    """Storage is a singleton thread-safe memory file store"""
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
                    raise FileNotFoundException("No file '{}' by that name".format(path))

        def put(self, path=None, file=None):
            if not path:
                raise EmptyPathException("Must supply a file path!")
            with self.mutex:
                if not file:
                    self.store.pop(path, None)
                else:
                    self.store[path] = file

    __instance = None

    def __new__(cls):
        if not Storage.__instance:
            Storage.__instance = Storage.__Storage()
        return Storage.__instance
