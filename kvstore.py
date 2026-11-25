"""Persistent key-value store using an append-only log."""

import json
import math
import os
import time

STRING_TYPE = "string"
HASH_TYPE = "hash"
LIST_TYPE = "list"


class KVStore:
    """Simple key-value database with append-only file storage."""

    def __init__(self, filename: str = "data.db") -> None:
        """Create a store and rebuild saved data if the file already exists.

        Args:
            filename: File used for append-only persistence.
        """
        self.data: list[list] = []
        self.filename = filename

        self.in_transaction = False
        self.backup_data: list[list] = []
        self.transaction_log: list[list] = []

        self.load_data()

    def find_key(self, key: str) -> int:
        """Find the position of a key.

        Args:
            key: Key to search for.

        Returns:
            The list index, or -1 if the key does not exist.
        """
        for i in range(len(self.data)):
            if self.data[i][0] == key:
                return i

        return -1

    def copy_data(self) -> list[list]:
        """Make a copy of the in-memory data for transaction rollback."""
        copied = []

        for item in self.data:
            key = item[0]
            data_type = item[1]
            value = item[2]
            expires_at = item[3]

            if data_type == HASH_TYPE:
                new_value = []

                for pair in value:
                    new_value.append([pair[0], pair[1]])

            elif data_type == LIST_TYPE:
                new_value = list(value)

            else:
                new_value = value

            copied.append([key, data_type, new_value, expires_at])

        return copied

    def write_log(self, record: list) -> None:
        """Save one operation to the append-only log.

        Args:
            record: Operation and arguments to save.
        """
        if self.in_transaction:
            self.transaction_log.append(record)
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def write_many(self, records: list[list]) -> None:
        """Save multiple operations after a transaction commit."""
        if len(records) == 0:
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.writelines(
                json.dumps(record) + "\n"
                for record in records
            )
            file.flush()
            os.fsync(file.fileno())

    def remove_expired(self, key: str) -> None:
        """Remove a key from memory if its expiration time has passed."""
        index = self.find_key(key)

        if index == -1:
            return

        expires_at = self.data[index][3]

        if expires_at is not None and expires_at <= time.time():
            self.data.pop(index)

    def set_value(self, key: str, value: str) -> None:
        """Update a string value in memory without writing to disk."""
        index = self.find_key(key)
        new_item = [key, STRING_TYPE, value, None]

        if index == -1:
            self.data.append(new_item)
        else:
            self.data[index] = new_item

    def set(
        self,
        key: str,
        value: str,
        save: bool = True,
    ) -> None:
        """Store or replace a value.

        Args:
            key: Key to store.
            value: Value to store.
            save: Whether to save the operation to disk.
        """
        self.set_value(key, value)

        if save:
            self.write_log(["SET", key, value])

    def get(self, key: str) -> str | None:
        """Get a string value.

        Args:
            key: Key to retrieve.

        Returns:
            The stored value, or None if it is missing or another data type.
        """
        self.remove_expired(key)
        index = self.find_key(key)

        if index == -1:
            return None

        if self.data[index][1] != STRING_TYPE:
            return None

        return self.data[index][2]

    def delete_value(self, key: str) -> int:
        """Delete a key from memory.

        Returns:
            1 if the key existed, otherwise 0.
        """
        self.remove_expired(key)
        index = self.find_key(key)

        if index == -1:
            return 0

        self.data.pop(index)

        return 1

    def delete(
        self,
        key: str,
        save: bool = True,
    ) -> int:
        """Delete a key.

        Args:
            key: Key to delete.
            save: Whether to save the operation to disk.

        Returns:
            1 if the key was deleted, otherwise 0.
        """
        result = self.delete_value(key)

        if result == 1 and save:
            self.write_log(["DEL", key])

        return result

    def exists(self, key: str) -> int:
        """Check whether a key exists.

        Args:
            key: Key to check.

        Returns:
            1 if the key exists, otherwise 0.
        """
        self.remove_expired(key)

        if self.find_key(key) == -1:
            return 0

        return 1

    def mset(
        self,
        items: list[str],
        save: bool = True,
    ) -> bool:
        """Store multiple key-value pairs.

        Args:
            items: Alternating keys and values.
            save: Whether to save the operation to disk.

        Returns:
            True if the input contains complete key-value pairs.
        """
        if len(items) == 0 or len(items) % 2 != 0:
            return False

        for i in range(0, len(items), 2):
            key = items[i]
            value = items[i + 1]

            self.set_value(key, value)

        if save:
            self.write_log(["MSET"] + items)

        return True

    def mget(
        self,
        keys: list[str],
    ) -> list[str | None]:
        """Get values for several keys.

        Args:
            keys: Keys to retrieve.

        Returns:
            Values in the same order as the requested keys.
        """
        values = []

        for key in keys:
            values.append(self.get(key))

        return values

    def expire_value(
        self,
        key: str,
        expires_at: float,
    ) -> int:
        """Set an absolute expiration time without writing to disk."""
        index = self.find_key(key)

        if index == -1:
            return 0

        self.data[index][3] = float(expires_at)

        return 1

    def expire(
        self,
        key: str,
        seconds: str | int,
    ) -> int:
        """Set a time-to-live on a key.

        Args:
            key: Key to expire.
            seconds: Number of seconds before expiration.

        Returns:
            1 if the expiration was set, otherwise 0.
        """
        try:
            seconds_int = int(seconds)
        except ValueError:
            return 0

        self.remove_expired(key)

        if self.find_key(key) == -1:
            return 0

        expires_at = time.time() + seconds_int

        self.expire_value(key, expires_at)
        self.write_log(
            ["EXPIREAT", key, expires_at]
        )

        return 1

    def ttl(self, key: str) -> int:
        """Get the remaining time-to-live.

        Args:
            key: Key to check.

        Returns:
            Remaining seconds, -1 for no expiration, or -2 if missing.
        """
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

    def range_keys(
        self,
        start: str,
        end: str,
    ) -> list[str]:
        """Return keys inside an inclusive lexicographical range.

        Args:
            start: Lower bound, or an empty string for no lower bound.
            end: Upper bound, or an empty string for no upper bound.

        Returns:
            Sorted keys inside the range.
        """
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
        """Start a transaction.

        Returns:
            True if a transaction started, otherwise False.
        """
        if self.in_transaction:
            return False

        self.backup_data = self.copy_data()
        self.transaction_log = []
        self.in_transaction = True

        return True

    def commit(self) -> bool:
        """Commit the active transaction.

        Returns:
            True if a transaction was committed, otherwise False.
        """
        if not self.in_transaction:
            return False

        records = list(self.transaction_log)

        self.in_transaction = False
        self.transaction_log = []
        self.backup_data = []

        self.write_many(records)

        return True

    def abort(self) -> bool:
        """Cancel the active transaction.

        Returns:
            True if a transaction was aborted, otherwise False.
        """
        if not self.in_transaction:
            return False

        self.data = self.backup_data
        self.backup_data = []
        self.transaction_log = []
        self.in_transaction = False

        return True

    def find_hash_field(
        self,
        fields: list[list],
        field: str,
    ) -> int:
        """Find the index of a field inside a hash."""
        for i in range(len(fields)):
            if fields[i][0] == field:
                return i

        return -1

    def hset_value(
        self,
        hash_name: str,
        field: str,
        value: str,
    ) -> int:
        """Set a hash field in memory without writing to disk."""
        self.remove_expired(hash_name)
        index = self.find_key(hash_name)

        if index == -1:
            self.data.append(
                [hash_name, HASH_TYPE, [], None]
            )
            index = self.find_key(hash_name)

        if self.data[index][1] != HASH_TYPE:
            return -1

        fields = self.data[index][2]
        field_index = self.find_hash_field(
            fields,
            field,
        )

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
        save: bool = True,
    ) -> int:
        """Set a field in a hash.

        Args:
            hash_name: Name of the hash.
            field: Field to store.
            value: Field value.
            save: Whether to save the operation to disk.

        Returns:
            1 for a new field, 0 for an update, or -1 on type mismatch.
        """
        result = self.hset_value(
            hash_name,
            field,
            value,
        )

        if result != -1 and save:
            self.write_log(
                ["HSET", hash_name, field, value]
            )

        return result

    def hget(
        self,
        hash_name: str,
        field: str,
    ) -> str | None:
        """Get one field from a hash.

        Args:
            hash_name: Name of the hash.
            field: Field to retrieve.

        Returns:
            The stored field value, or None if it was not found.
        """
        self.remove_expired(hash_name)
        index = self.find_key(hash_name)

        if index == -1:
            return None

        if self.data[index][1] != HASH_TYPE:
            return None

        fields = self.data[index][2]
        field_index = self.find_hash_field(
            fields,
            field,
        )

        if field_index == -1:
            return None

        return fields[field_index][1]

    def hgetall(
        self,
        hash_name: str,
    ) -> list[list]:
        """Return every field-value pair in a hash."""
        self.remove_expired(hash_name)
        index = self.find_key(hash_name)

        if index == -1:
            return []

        if self.data[index][1] != HASH_TYPE:
            return []

        return self.data[index][2]

    def get_or_make_list(
        self,
        key: str,
    ) -> list | None:
        """Get a list or create an empty one if the key is missing."""
        self.remove_expired(key)
        index = self.find_key(key)

        if index == -1:
            self.data.append(
                [key, LIST_TYPE, [], None]
            )
            index = self.find_key(key)

        if self.data[index][1] != LIST_TYPE:
            return None

        return self.data[index][2]

    def lpush_value(
        self,
        key: str,
        value: str,
    ) -> int:
        """Prepend a value to a list in memory."""
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.insert(0, value)

        return len(values)

    def lpush(
        self,
        key: str,
        value: str,
        save: bool = True,
    ) -> int:
        """Prepend a value to a list.

        Returns:
            The new list length, or -1 on a type mismatch.
        """
        length = self.lpush_value(key, value)

        if length != -1 and save:
            self.write_log(
                ["LPUSH", key, value]
            )

        return length

    def rpush_value(
        self,
        key: str,
        value: str,
    ) -> int:
        """Append a value to a list in memory."""
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.append(value)

        return len(values)

    def rpush(
        self,
        key: str,
        value: str,
        save: bool = True,
    ) -> int:
        """Append a value to a list.

        Returns:
            The new list length, or -1 on a type mismatch.
        """
        length = self.rpush_value(key, value)

        if length != -1 and save:
            self.write_log(
                ["RPUSH", key, value]
            )

        return length

    def lrange(
        self,
        key: str,
        start: str | int,
        stop: str | int,
    ) -> list:
        """Return an inclusive range of list elements.

        Args:
            key: List key.
            start: Starting index.
            stop: Ending index.

        Returns:
            Values inside the requested range.
        """
        self.remove_expired(key)
        index = self.find_key(key)

        if index == -1:
            return []

        if self.data[index][1] != LIST_TYPE:
            return []

        try:
            start_int = int(start)
            stop_int = int(stop)
        except ValueError:
            return []

        values = self.data[index][2]
        length = len(values)

        if start_int < 0:
            start_int = length + start_int

        if stop_int < 0:
            stop_int = length + stop_int

        start_int = max(start_int, 0)

        if stop_int >= length:
            stop_int = length - 1

        if (
            start_int > stop_int
            or start_int >= length
        ):
            return []

        return values[
            start_int:stop_int + 1
        ]

    def lpop_value(
        self,
        key: str,
    ) -> str | None:
        """Remove and return the first list value in memory."""
        self.remove_expired(key)
        index = self.find_key(key)

        if index == -1:
            return None

        if self.data[index][1] != LIST_TYPE:
            return None

        values = self.data[index][2]

        if len(values) == 0:
            return None

        return values.pop(0)

    def lpop(
        self,
        key: str,
        save: bool = True,
    ) -> str | None:
        """Remove and return the first value in a list."""
        value = self.lpop_value(key)

        if value is not None and save:
            self.write_log(["LPOP", key])

        return value

    def change_counter(
        self,
        key: str,
        amount: int,
    ) -> int | None:
        """Change a numeric key by an amount.

        Returns:
            The new number, or None if the existing value is not numeric.
        """
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
        """Increment a numeric key and return the new value."""
        return self.change_counter(
            key,
            1,
        )

    def decr(self, key: str) -> int | None:
        """Decrement a numeric key and return the new value."""
        return self.change_counter(
            key,
            -1,
        )

    def flushdb(
        self,
        save: bool = True,
    ) -> None:
        """Delete every key in the database.

        Args:
            save: Whether to save the operation to disk.
        """
        self.data = []

        if save:
            self.write_log(["FLUSHDB"])

    def replay(self, record: list) -> None:
        """Replay one saved operation while rebuilding the database."""
        if len(record) == 0:
            return

        command = record[0]

        if command == "SET":
            self.set(
                record[1],
                record[2],
                save=False,
            )

        elif command == "DEL":
            self.delete(
                record[1],
                save=False,
            )

        elif command == "MSET":
            self.mset(
                record[1:],
                save=False,
            )

        elif command == "EXPIREAT":
            self.expire_value(
                record[1],
                record[2],
            )

        elif command == "HSET":
            self.hset(
                record[1],
                record[2],
                record[3],
                save=False,
            )

        elif command == "LPUSH":
            self.lpush(
                record[1],
                record[2],
                save=False,
            )

        elif command == "RPUSH":
            self.rpush(
                record[1],
                record[2],
                save=False,
            )

        elif command == "LPOP":
            self.lpop(
                record[1],
                save=False,
            )

        elif command == "FLUSHDB":
            self.flushdb(
                save=False,
            )

    def load_data(self) -> None:
        """Rebuild the in-memory state from the append-only log."""
        if not os.path.exists(self.filename):
            return

        with open(
            self.filename,
            "r",
            encoding="utf-8",
        ) as file:
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
                    TypeError,
                ):
                    continue