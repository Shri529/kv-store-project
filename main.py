import shlex

from kvstore import KVStore

db = KVStore()


while True:
    try:
        user_input = input().strip()
    except EOFError:
        break

    if user_input == "":
        continue

    try:
        parts = shlex.split(user_input)
    except ValueError:
        print("Invalid command", flush=True)
        continue

    if len(parts) == 0:
        continue

    command = parts[0].upper()

    if command == "SET" and len(parts) >= 3:
        key = parts[1]
        value = " ".join(parts[2:])

        db.set(key, value)

        print("OK", flush=True)

    elif command == "GET" and len(parts) == 2:
        value = db.get(parts[1])

        if value is not None:
            print(value, flush=True)

    elif command == "DEL" and len(parts) == 2:
        print(
            db.delete(parts[1]),
            flush=True
        )

    elif command == "EXISTS" and len(parts) == 2:
        print(
            db.exists(parts[1]),
            flush=True
        )

    elif command == "MSET" and len(parts) >= 3:
        worked = db.mset(parts[1:])

        if worked:
            print("OK", flush=True)
        else:
            print("Invalid command", flush=True)

    elif command == "MGET" and len(parts) >= 2:
        values = db.mget(parts[1:])

        for value in values:
            if value is None:
                print("nil", flush=True)
            else:
                print(value, flush=True)

    elif command == "EXPIRE" and len(parts) == 3:
        print(
            db.expire(parts[1], parts[2]),
            flush=True
        )

    elif command == "TTL" and len(parts) == 2:
        print(
            db.ttl(parts[1]),
            flush=True
        )

    elif command == "RANGE" and len(parts) == 3:
        keys = db.range_keys(parts[1], parts[2])

        for key in keys:
            print(key, flush=True)

        print("END", flush=True)

    elif command == "BEGIN" and len(parts) == 1:
        if db.begin():
            print("OK", flush=True)
        else:
            print("Invalid command", flush=True)

    elif command == "COMMIT" and len(parts) == 1:
        if db.commit():
            print("OK", flush=True)
        else:
            print("Invalid command", flush=True)

    elif command == "ABORT" and len(parts) == 1:
        if db.abort():
            print("OK", flush=True)
        else:
            print("Invalid command", flush=True)

    elif command == "HSET" and len(parts) >= 4:
        hash_name = parts[1]
        field = parts[2]
        value = " ".join(parts[3:])

        print(
            db.hset(hash_name, field, value),
            flush=True
        )

    elif command == "HGET" and len(parts) == 3:
        value = db.hget(parts[1], parts[2])

        if value is not None:
            print(value, flush=True)

    elif command == "HGETALL" and len(parts) == 2:
        fields = db.hgetall(parts[1])

        for field, value in fields:
            print(field, value, flush=True)

    elif command == "LPUSH" and len(parts) >= 3:
        key = parts[1]
        value = " ".join(parts[2:])

        print(
            db.lpush(key, value),
            flush=True
        )

    elif command == "RPUSH" and len(parts) >= 3:
        key = parts[1]
        value = " ".join(parts[2:])

        print(
            db.rpush(key, value),
            flush=True
        )

    elif command == "LRANGE" and len(parts) == 4:
        values = db.lrange(
            parts[1],
            parts[2],
            parts[3]
        )

        for value in values:
            print(value, flush=True)

    elif command == "LPOP" and len(parts) == 2:
        value = db.lpop(parts[1])

        if value is not None:
            print(value, flush=True)

    elif command == "INCR" and len(parts) == 2:
        value = db.incr(parts[1])

        if value is None:
            print("Invalid command", flush=True)
        else:
            print(value, flush=True)

    elif command == "DECR" and len(parts) == 2:
        value = db.decr(parts[1])

        if value is None:
            print("Invalid command", flush=True)
        else:
            print(value, flush=True)

    elif command == "FLUSHDB" and len(parts) == 1:
        db.flushdb()

        print("OK", flush=True)

    elif command == "EXIT" and len(parts) == 1:
        break

    else:
        print("Invalid command", flush=True)