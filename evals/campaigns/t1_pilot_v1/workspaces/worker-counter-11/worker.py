from threading import Lock

counter = 0
counter_lock = Lock()


def record_success():
    global counter
    with counter_lock:
        counter += 1
