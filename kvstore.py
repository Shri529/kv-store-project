"""Persistent key-value store using an append-only log."""

import json
import math
import os
import time


class KVStore:
    """Simple key-value database with append-only file storage."""
    
    def __init__(self, filename: str = "data.db") -> None:
        self.data = []
        self.filename = filename

        self.in_transaction = False
        self.backup_data = []
        self.transaction_log = []

        self.load_data()

    def find_key(self, key: str) -> int:
        """Find the position of a key in the list."""
        for i in range(len(self.data)):
            if self.data[i][0] == key:
                return i

        return -1

    def copy_data(self):
        copied = []

        for item in self.data:
            key = item[0]
            data_type = item[1]
            value = item[2]
            expires_at = item[3]

            if data_type == "hash":
                new_value = []

                for pair in value:
                    new_value.append([pair[0], pair[1]])

            elif data_type == "list":
                new_value = list(value)

            else:
                new_value = value

            copied.append([key, data_type, new_value, expires_at])

        return copied

    def write_log(self, record: list) -> None:
        """Save one database operation to the log file."""
        if self.in_transaction:
            self.transaction_log.append(record)
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def write_many(self, records: list) -> None:
        """Save multiple database operations to the log file."""
        if len(records) == 0:
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.writelines(json.dumps(record) + "\n" for record in records)

            file.flush()
            os.fsync(file.fileno())

    def remove_expired(self, key: str) -> None:
        index = self.find_key(key)

        if index == -1:
            return

        expires_at = self.data[index][3]

        if expires_at is not None and expires_at <= time.time():
            self.data.pop(index)

    def set_value(self, key: str, value: str) -> None:
        index = self.find_key(key)
        new_item = [key, "string", value, None]

        if index == -1:
            self.data.append(new_item)
        else:
            self.data[index] = new_item

    def set(self, key: str, value: str, save: bool = True) -> None:
        """Store or replace a key and value."""
        self.set_value(key, value)

        if save:
            self.write_log(["SET", key, value])

    def get(self, key: str) -> str | None:
        """Return the value for a key if it exists."""
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return None

        if self.data[index][1] != "string":
            return None

        return self.data[index][2]

    def delete_value(self, key: str) -> int:
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return 0

        self.data.pop(index)

        return 1

    def delete(self, key: str, save: bool = True) -> int:
        """Delete a key from the database."""
        result = self.delete_value(key)

        if result == 1 and save:
            self.write_log(["DEL", key])

        return result

    def exists(self, key: str) -> int:
        self.remove_expired(key)

        if self.find_key(key) == -1:
            return 0

        return 1

    def mset(self, items: list[str], save: bool = True) -> bool:
        if len(items) == 0 or len(items) % 2 != 0:
            return False

        for i in range(0, len(items), 2):
            key = items[i]
            value = items[i + 1]

            self.set_value(key, value)

        if save:
            self.write_log(["MSET"] + items)

        return True

    def mget(self, keys: list[str]) -> list:
        values = []

        for key in keys:
            values.append(self.get(key))

        return values

    def expire_value(self, key: str, expires_at: float) -> int:
        index = self.find_key(key)

        if index == -1:
            return 0

        self.data[index][3] = float(expires_at)

        return 1

    def expire(self, key: str, seconds: str) -> int:
        """Give a key an expiration time."""
        try:
            seconds = int(seconds)
        except ValueError:
            return 0

        self.remove_expired(key)

        if self.find_key(key) == -1:
            return 0

        expires_at = time.time() + seconds

        self.expire_value(key, expires_at)
        self.write_log(["EXPIREAT", key, expires_at])

        return 1

    def ttl(self, key: str) -> int:
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return -2

        expires_at = self.data[index][3]

        if expires_at is None:
            return -1

        remaining = expires_at - time.time()

        if remaining <= 0:
            self.data.pop(index)
            return -2

        return math.ceil(remaining)

    def range_keys(self, start: str, end: str) -> list[str]:
        """Return keys inside a lexicographical range."""
        keys = []

        current_keys = []

        for item in self.data:
            current_keys.append(item[0])

        for key in current_keys:
            self.remove_expired(key)

        for item in self.data:
            key = item[0]

            start_ok = start == "" or key >= start
            end_ok = end == "" or key <= end

            if start_ok and end_ok:
                keys.append(key)

        keys.sort()

        return keys

    def begin(self) -> bool:
        """Start a transaction."""
        if self.in_transaction:
            return False

        self.backup_data = self.copy_data()
        self.transaction_log = []
        self.in_transaction = True

        return True

    def commit(self) -> bool:
        """Save all operations in the current transaction."""
        if not self.in_transaction:
            return False

        records = list(self.transaction_log)

        self.in_transaction = False
        self.transaction_log = []
        self.backup_data = []

        self.write_many(records)

        return True

    def abort(self) -> bool:
        """Cancel the current transaction."""
        if not self.in_transaction:
            return False

        self.data = self.backup_data
        self.backup_data = []
        self.transaction_log = []
        self.in_transaction = False

        return True

    def find_hash_field(self, fields: list, field: str) -> int:
        for i in range(len(fields)):
            if fields[i][0] == field:
                return i

        return -1

    def hset_value(self, hash_name: str, field: str, value: str) -> int:
        self.remove_expired(hash_name)

        index = self.find_key(hash_name)

        if index == -1:
            self.data.append([hash_name, "hash", [], None])
            index = self.find_key(hash_name)

        if self.data[index][1] != "hash":
            return -1

        fields = self.data[index][2]

        field_index = self.find_hash_field(fields, field)

        if field_index == -1:
            fields.append([field, value])
            return 1

        fields[field_index][1] = value

        return 0

    def hset(
        self,
        hash_name: str,
        field: str,
        value: str,
        save: bool = True
) -> int:
        result = self.hset_value(hash_name, field, value)

        if result != -1 and save:
            self.write_log(["HSET", hash_name, field, value])

        return result

    def hget(self, hash_name: str, field: str) -> str | None:
        self.remove_expired(hash_name)

        index = self.find_key(hash_name)

        if index == -1:
            return None

        if self.data[index][1] != "hash":
            return None

        fields = self.data[index][2]

        field_index = self.find_hash_field(fields, field)

        if field_index == -1:
            return None

        return fields[field_index][1]

    def hgetall(self, hash_name: str) -> list:
        self.remove_expired(hash_name)

        index = self.find_key(hash_name)

        if index == -1:
            return []

        if self.data[index][1] != "hash":
            return []

        return self.data[index][2]

    def get_or_make_list(self, key: str) -> list | None:
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            self.data.append([key, "list", [], None])
            index = self.find_key(key)

        if self.data[index][1] != "list":
            return None

        return self.data[index][2]

    def lpush_value(self, key: str, value: str) -> int:
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.insert(0, value)

        return len(values)

    def lpush(self, key: str, value: str, save: bool = True) -> int:
        length = self.lpush_value(key, value)

        if length != -1 and save:
            self.write_log(["LPUSH", key, value])

        return length

    def rpush_value(self, key: str, value: str) -> int:
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.append(value)

        return len(values)

    def rpush(self, key: str, value: str, save: bool = True) -> int:
        length = self.rpush_value(key, value)

        if length != -1 and save:
            self.write_log(["RPUSH", key, value])

        return length

    def lrange(self, key: str, start: str, stop: str) -> list:
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return []

        if self.data[index][1] != "list":
            return []

        try:
            start = int(start)
            stop = int(stop)
        except ValueError:
            return []

        values = self.data[index][2]
        length = len(values)

        if start < 0:
            start = length + start

        if stop < 0:
            stop = length + stop

        start = max(start, 0)

        if stop >= length:
            stop = length - 1

        if start > stop or start >= length:
            return []

        return values[start:stop + 1]

    def lpop_value(self, key: str) -> str | None:
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return None

        if self.data[index][1] != "list":
            return None

        values = self.data[index][2]

        if len(values) == 0:
            return None

        return values.pop(0)

    def lpop(self, key: str, save: bool = True) -> str | None:
        value = self.lpop_value(key)

        if value is not None and save:
            self.write_log(["LPOP", key])

        return value

    def change_counter(self, key: str, amount: int) -> int | None:
        current = self.get(key)

        if current is None:
            number = 0
        else:
            try:
                number = int(current)
            except ValueError:
                return None

        number += amount

        self.set(key, str(number))

        return number

    def incr(self, key: str) -> int | None:
        return self.change_counter(key, 1)

    def decr(self, key: str) -> int | None:
        return self.change_counter(key, -1)

    def flushdb(self, save: bool = True) -> None:
        self.data = []

        if save:
            self.write_log(["FLUSHDB"])

    def replay(self, record: list) -> None:
        """Replay one saved operation when the database starts."""
        if len(record) == 0:
            return

        command = record[0]

        if command == "SET":
            self.set(record[1], record[2], save=False)

        elif command == "DEL":
            self.delete(record[1], save=False)

        elif command == "MSET":
            self.mset(record[1:], save=False)

        elif command == "EXPIREAT":
            self.expire_value(record[1], record[2])

        elif command == "HSET":
            self.hset(
                record[1],
                record[2],
                record[3],
                save=False
            )

        elif command == "LPUSH":
            self.lpush(
                record[1],
                record[2],
                save=False
            )

        elif command == "RPUSH":
            self.rpush(
                record[1],
                record[2],
                save=False
            )

        elif command == "LPOP":
            self.lpop(record[1], save=False)

        elif command == "FLUSHDB":
            self.flushdb(save=False)

    def load_data(self) -> None:
        """Rebuild the in-memory data from data.db."""
        if not os.path.exists(self.filename):
            return

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if line == "":
                    continue

                try:
                    record = json.loads(line)
                    self.replay(record)

                except (
                    json.JSONDecodeError,
                    IndexError,
                    ValueError,
                    TypeError
                ):
                    continue
