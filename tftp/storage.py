import threading

class ErrorEmptyPath(Exception):
    pass

class ErrorFileNotFound(Exception):
    pass

class ErrorFileExists(Exception):
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
                raise ErrorEmptyPath("Must supply a file path!")
            with self.mutex:
                if path in self.store:
                    return self.store[path]
                else:
                    raise ErrorFileNotFound("No such file '{}'".format(path))

        def put(self, path=None, file=None):
            if not path:
                raise ErrorEmptyPath("Must supply a file path!")
            with self.mutex:
                if path in self.store:
                    raise ErrorFileExists("File '{}' already exists!".format(path))
                else:
                    self.store[path] = file
