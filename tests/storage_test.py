import unittest
import context
from tftp import storage

class TestStorage(unittest.TestCase):
    file = 0x0123456789ABCDEF
    fileName = "a_filename"
    def test_singleton(self):
        a = storage.Storage()
        b = storage.Storage()
        self.assertEqual(a, b)

    def test_getEmptyPath(self):
        a = storage.Storage()
        self.assertRaises(
            storage.EmptyPathException,
            a.get)

    def test_getFileNotFound(self):
        a = storage.Storage()
        self.assertRaises(
            storage.FileNotFoundException,
            a.get,
            "not_a_file")

    def test_putEmptyPath(self):
        a = storage.Storage()
        self.assertRaises(
            storage.EmptyPathException,
            a.put)

    def test_putCreatesFile(self):
        a = storage.Storage()
        a.put(self.fileName, self.file)
        self.assertIn(self.fileName, a.store)

    def test_getFile(self):
        a = storage.Storage()
        a.put(self.fileName, self.file)
        t = a.get(self.fileName)
        self.assertEqual(self.file, t)

    def test_putRemovesFile(self):
        a = storage.Storage()
        a.put(self.fileName, self.file)
        self.assertIn(self.fileName, a.store)
        a.put(self.fileName, None)
        self.assertRaises(
            storage.FileNotFoundException,
            a.get,
            self.fileName)


if __name__ == '__main__':
    unittest.main()
