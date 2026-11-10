import sys
import threading
from datetime import datetime
from pathlib import Path


class PrintLogger:
    """Replaces sys.stdout / sys.stderr and copies every write to several streams.

    setup_print_logging() assigns instances to sys.stdout and sys.stderr, so each print() ends up in
    write() here and is forwarded to the original terminal and associated log files. Each write() holds 
    a lock so the streams stay consistent, but print() sends the text and the trailing newline as separate 
    writes, so lines from different threads can still interleave.
    """

    def __init__(self, *streams, lock=None):
        self._streams = list(streams)
        self._lock = lock if lock is not None else threading.RLock()

    def write(self, message):
        with self._lock:
            for stream in self._streams:
                stream.write(message)
                stream.flush()
        return len(message)

    def flush(self):
        with self._lock:
            for stream in self._streams:
                stream.flush()

    def isatty(self):
        with self._lock:
            return any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)

    def add_stream(self, stream):
        with self._lock:
            self._streams.append(stream)

    def remove_stream(self, stream):
        with self._lock:
            if stream in self._streams:
                self._streams.remove(stream)


_output_lock = threading.RLock()
_stdout_mirror = None
_stderr_mirror = None
_experiment_log_file = None


def setup_print_logging(log_dir, log_filename=None):
    """Duplicate everything write to stdout/stderr (every print()) into a log file under
    log_dir alongside the terminal. Called as early as possible.
    Raises RuntimeError if print logging has already been configured in this process.
    """
    global _stdout_mirror, _stderr_mirror
    with _output_lock:
        if _stdout_mirror is not None or _stderr_mirror is not None:
            raise RuntimeError("Print logging has already been configured")

        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_filename = log_filename or datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
        log_path = log_dir / log_filename
        log_file = open(log_path, "a", buffering=1, encoding="utf-8")

        _stdout_mirror = PrintLogger(sys.stdout, log_file, lock=_output_lock)
        _stderr_mirror = PrintLogger(sys.stderr, log_file, lock=_output_lock)
        sys.stdout = _stdout_mirror
        sys.stderr = _stderr_mirror
        return log_path


def set_experiment_log_target(folder_path, log_filename="frontend.log"):
    """Also mirrors all output into experiment 'logs' folder, alongside the global log.
    Replaces any previously attached experiment log (e.g. when switching to a different experiment).
    Nothing done if setup_print_logging() hasn't been called yet. Default name is frontend.log
    """
    global _experiment_log_file
    if _stdout_mirror is None or _stderr_mirror is None:
        return None

    log_dir = Path(folder_path) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename
    new_file = open(log_path, "a", buffering=1, encoding="utf-8")

    with _output_lock:
        if _experiment_log_file is not None:
            _stdout_mirror.remove_stream(_experiment_log_file)
            _stderr_mirror.remove_stream(_experiment_log_file)
            _experiment_log_file.close()

        _stdout_mirror.add_stream(new_file)
        _stderr_mirror.add_stream(new_file)
        _experiment_log_file = new_file
    return log_path
