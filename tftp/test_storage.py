import unittest
import uuid
import storage

class TestStorage(unittest.TestCase):
    def test_singleton(self):
        a = storage.Storage()
        b = storage.Storage()
        self.assertEqual(a, b)

    def test_getEmptyPath(self):
        a = storage.Storage()
        self.assertRaises(
            storage.ErrorEmptyPath,
            a.get)

    def test_getFileNotFound(self):
        a = storage.Storage()
        self.assertRaises(
            storage.ErrorFileNotFound,
            a.get,
            "not_a_file")

    def test_putEmptyPath(self):
        a = storage.Storage()
        self.assertRaises(
            storage.ErrorEmptyPath,
            a.put)

    def test_putCreatesFile(self):
        file = uuid.uuid1()
        fileName = uuid.uuid1()
        a = storage.Storage()
        a.put(fileName, file)
        self.assertIn(fileName, a.store)

    def test_getFile(self):
        file = uuid.uuid1()
        fileName = uuid.uuid1()
        a = storage.Storage()
        a.put(fileName, file)
        t = a.get(fileName)
        self.assertEqual(file, t)

    def test_putFileExists(self):
        file = uuid.uuid1()
        fileName = uuid.uuid1()
        a = storage.Storage()
        a.put(fileName, file)
        self.assertIn(fileName, a.store)
        self.assertRaises(
            storage.ErrorFileExists,
            a.put,
            fileName)


if __name__ == '__main__':
    unittest.main()
