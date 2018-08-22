import threading

class ErrorEmptyPath(Exception):
    pass

class ErrorFileNotFound(Exception):
    pass

class ErrorFileExists(Exception):
    pass

class Storage(object):
    """Maintains a singleton of an in-memory dictionary for file storage."""
    __instance = None

    def __new__(cls):
        if not Storage.__instance:
            Storage.__instance = Storage.__Storage()
        return Storage.__instance

    class __Storage():
        def __init__(self):
            self.store = {}
            self.mutex = threading.Lock()

        def get(self, path=None):
            with self.mutex:
                if not path:
                    raise ErrorEmptyPath("Must supply a file path!")
                if path in self.store:
                    return self.store[path]
                else:
                    raise ErrorFileNotFound("No such file '{}'".format(path))

        def put(self, path=None, file=None):
            with self.mutex:
                if not path:
                    raise ErrorEmptyPath("Must supply a file path!")
                if path in self.store:
                    raise ErrorFileExists("File '{}' already exists!".format(path))
                else:
                    self.store[path] = file
