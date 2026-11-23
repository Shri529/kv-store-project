import os
import unittest

from kvstore import KVStore


class TestKVStore(unittest.TestCase):
    def setUp(self):
        self.filename = "test_data.db"

        if os.path.exists(self.filename):
            os.remove(self.filename)

        self.db = KVStore(self.filename)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_set_and_get(self):
        self.db.set("name", "Shri")

        self.assertEqual(self.db.get("name"), "Shri")

    def test_overwrite(self):
        self.db.set("name", "Shri")
        self.db.set("name", "Yuki")

        self.assertEqual(self.db.get("name"), "Yuki")

    def test_delete_and_exists(self):
        self.db.set("test", "hello")

        self.assertEqual(self.db.exists("test"), 1)

        self.db.delete("test")

        self.assertEqual(self.db.exists("test"), 0)
        self.assertIsNone(self.db.get("test"))

    def test_mset_and_mget(self):
        self.db.mset([
            "a", "apple",
            "b", "banana"
        ])

        values = self.db.mget(["b", "a", "missing"])

        self.assertEqual(
            values,
            ["banana", "apple", None]
        )

    def test_persistence(self):
        self.db.set("saved", "yes")

        new_db = KVStore(self.filename)

        self.assertEqual(
            new_db.get("saved"),
            "yes"
        )

    def test_counter(self):
        self.assertEqual(self.db.incr("count"), 1)
        self.assertEqual(self.db.incr("count"), 2)
        self.assertEqual(self.db.decr("count"), 1)

    def test_transaction_abort(self):
        self.db.begin()

        self.db.set("temp", "value")

        self.assertEqual(
            self.db.get("temp"),
            "value"
        )

        self.db.abort()

        self.assertIsNone(
            self.db.get("temp")
        )

    def test_list(self):
        self.db.lpush("list", "one")
        self.db.rpush("list", "two")

        self.assertEqual(
            self.db.lrange("list", 0, -1),
            ["one", "two"]
        )


if __name__ == "__main__":
    unittest.main()