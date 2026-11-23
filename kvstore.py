import json
import math
import os
import time


class KVStore:
    def __init__(self, filename="data.db"):
        self.data = []
        self.filename = filename

        self.in_transaction = False
        self.backup_data = []
        self.transaction_log = []

        self.load_data()

    def find_key(self, key):
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

    def write_log(self, record):
        if self.in_transaction:
            self.transaction_log.append(record)
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def write_many(self, records):
        if len(records) == 0:
            return

        with open(self.filename, "a", encoding="utf-8") as file:
            file.writelines(json.dumps(record) + "\n" for record in records)

            file.flush()
            os.fsync(file.fileno())

    def remove_expired(self, key):
        index = self.find_key(key)

        if index == -1:
            return

        expires_at = self.data[index][3]

        if expires_at is not None and expires_at <= time.time():
            self.data.pop(index)

    def set_value(self, key, value):
        index = self.find_key(key)
        new_item = [key, "string", value, None]

        if index == -1:
            self.data.append(new_item)
        else:
            self.data[index] = new_item

    def set(self, key, value, save=True):
        self.set_value(key, value)

        if save:
            self.write_log(["SET", key, value])

    def get(self, key):
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return None

        if self.data[index][1] != "string":
            return None

        return self.data[index][2]

    def delete_value(self, key):
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            return 0

        self.data.pop(index)

        return 1

    def delete(self, key, save=True):
        result = self.delete_value(key)

        if result == 1 and save:
            self.write_log(["DEL", key])

        return result

    def exists(self, key):
        self.remove_expired(key)

        if self.find_key(key) == -1:
            return 0

        return 1

    def mset(self, items, save=True):
        if len(items) == 0 or len(items) % 2 != 0:
            return False

        for i in range(0, len(items), 2):
            key = items[i]
            value = items[i + 1]

            self.set_value(key, value)

        if save:
            self.write_log(["MSET"] + items)

        return True

    def mget(self, keys):
        values = []

        for key in keys:
            values.append(self.get(key))

        return values

    def expire_value(self, key, expires_at):
        index = self.find_key(key)

        if index == -1:
            return 0

        self.data[index][3] = float(expires_at)

        return 1

    def expire(self, key, seconds):
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

    def ttl(self, key):
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

    def range_keys(self, start, end):
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

    def begin(self):
        if self.in_transaction:
            return False

        self.backup_data = self.copy_data()
        self.transaction_log = []
        self.in_transaction = True

        return True

    def commit(self):
        if not self.in_transaction:
            return False

        records = list(self.transaction_log)

        self.in_transaction = False
        self.transaction_log = []
        self.backup_data = []

        self.write_many(records)

        return True

    def abort(self):
        if not self.in_transaction:
            return False

        self.data = self.backup_data
        self.backup_data = []
        self.transaction_log = []
        self.in_transaction = False

        return True

    def find_hash_field(self, fields, field):
        for i in range(len(fields)):
            if fields[i][0] == field:
                return i

        return -1

    def hset_value(self, hash_name, field, value):
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

    def hset(self, hash_name, field, value, save=True):
        result = self.hset_value(hash_name, field, value)

        if result != -1 and save:
            self.write_log(["HSET", hash_name, field, value])

        return result

    def hget(self, hash_name, field):
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

    def hgetall(self, hash_name):
        self.remove_expired(hash_name)

        index = self.find_key(hash_name)

        if index == -1:
            return []

        if self.data[index][1] != "hash":
            return []

        return self.data[index][2]

    def get_or_make_list(self, key):
        self.remove_expired(key)

        index = self.find_key(key)

        if index == -1:
            self.data.append([key, "list", [], None])
            index = self.find_key(key)

        if self.data[index][1] != "list":
            return None

        return self.data[index][2]

    def lpush_value(self, key, value):
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.insert(0, value)

        return len(values)

    def lpush(self, key, value, save=True):
        length = self.lpush_value(key, value)

        if length != -1 and save:
            self.write_log(["LPUSH", key, value])

        return length

    def rpush_value(self, key, value):
        values = self.get_or_make_list(key)

        if values is None:
            return -1

        values.append(value)

        return len(values)

    def rpush(self, key, value, save=True):
        length = self.rpush_value(key, value)

        if length != -1 and save:
            self.write_log(["RPUSH", key, value])

        return length

    def lrange(self, key, start, stop):
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

    def lpop_value(self, key):
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

    def lpop(self, key, save=True):
        value = self.lpop_value(key)

        if value is not None and save:
            self.write_log(["LPOP", key])

        return value

    def change_counter(self, key, amount):
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

    def incr(self, key):
        return self.change_counter(key, 1)

    def decr(self, key):
        return self.change_counter(key, -1)

    def flushdb(self, save=True):
        self.data = []

        if save:
            self.write_log(["FLUSHDB"])

    def replay(self, record):
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

    def load_data(self):
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