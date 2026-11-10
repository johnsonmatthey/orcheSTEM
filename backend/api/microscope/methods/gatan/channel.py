import threading
import queue
import time


class GMSChannel:
    """
    Channel for GMS coms. DM constantly polls for next queued command where results are then posted back.
    """
    def __init__(self):
        self._command_queue = queue.Queue()  # Queue commands without blocking and this is what gms will poll form
        self._result_store = {} # stores any results posted back from gms for submit_command to retrieve and return it
        self._result_events = {} #stores threading events for each command id so submit_command can block until the result is posted back by gms
        self._lock = threading.Lock()
        self._cmd_counter = 0
        self._last_poll_time = None  # timestamp of last GMS poll

    def _next_id(self):
        with self._lock:
            self._cmd_counter += 1
            return self._cmd_counter

    def submit_command(self, command: str, params: dict = None, timeout: float = 120.0) -> dict:
        """
        Queues a command for DM and blocks until the result arrives via threading events
        """
        cmd_id = self._next_id()
        event = threading.Event()
        self._result_events[cmd_id] = event
        self._command_queue.put(
            {
                "id": cmd_id,
                "command": command,
                "params" : params if params else {}
            }
        )
        print(f"Submitted command {command} with params {params} and id {cmd_id}")

        if not event.wait(timeout=timeout):
            self._result_events.pop(cmd_id, None)
            self._result_store.pop(cmd_id, None)  # clean up in case GMS posted between timeout and here
            return {"ok": False, "id": cmd_id, "error": "timeout"}

        result = self._result_store.pop(cmd_id, None)
        self._result_events.pop(cmd_id, None)
        return {"ok": True, "id": cmd_id, "result": result}

    def poll_next(self) -> dict:
        """Called by get /gms/poll"""
        self._last_poll_time = time.monotonic()
        try:
            item = self._command_queue.get_nowait()
            return {"ok": True, "id": item["id"], "command": item["command"], "params": item.get("params", {})}
        except queue.Empty:
            return {"ok": True, "id": None, "command": None, "params": None}

    def post_result(self, cmd_id: int, result) -> dict:
        """Called by POST /gms/result — wakes up the waiting submit_command."""
        self._result_store[cmd_id] = result
        event = self._result_events.get(cmd_id)
        if event:
            event.set()  # threading.Event.set() — wakes the blocking .wait() in submit_command
        return {"ok": True}

    def is_connected(self, timeout_s: float = 6000.0) -> tuple[bool, float | None]:
        """(connected, seconds since the last GMS poll or None if never polled) - connected means polled within timeout_s."""
        if self._last_poll_time is None:
            print("Checking GMS connection. No poll received yet.")
            return False, None
        elapsed = time.monotonic() - self._last_poll_time
        print(f"Checking GMS connection. Last poll was {elapsed:.2f} seconds ago.")
        return elapsed < timeout_s, elapsed
