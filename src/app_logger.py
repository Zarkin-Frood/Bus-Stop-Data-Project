import logging
import logging.handlers
import os
import sys
import threading


class AppLogger:
    """
    Owns the app's logging setup. Create ONE in main(), then hand each class its
    own child logger:

        app_log = AppLogger()
        crime_service = CrimeStatsService(logger=app_log.get("crime"))

    Handlers hang off a named logger ("busstop"), not the root logger, so this
    doesn't change how other libraries log. Children such as "busstop.crime"
    propagate up to it automatically.

    Output:
      console      INFO and above
      app.log      INFO and above (rotating)
      errors.log   WARNING and above, including exception tracebacks (rotating)
    """

    FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

    def __init__(self, name="busstop", log_dir="data", level=logging.INFO,
                 console=True, files=True, max_bytes=2_000_000, backup_count=3):
        self.name = name
        self.log_dir = log_dir
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.propagate = False
        self._configure(console, files, max_bytes, backup_count)

    # ---------- setup ----------

    def _configure(self, console, files, max_bytes, backup_count):
        self.close()  # safe to construct more than once (tests, reloads)
        formatter = logging.Formatter(self.FORMAT)

        def add(handler, level):
            handler.setLevel(level)
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        if console:
            add(logging.StreamHandler(), logging.INFO)
        if files:
            os.makedirs(self.log_dir, exist_ok=True)
            for filename, level in (("app.log", logging.INFO),
                                    ("errors.log", logging.WARNING)):
                add(logging.handlers.RotatingFileHandler(
                    os.path.join(self.log_dir, filename),
                    maxBytes=max_bytes, backupCount=backup_count,
                    encoding="utf-8"), level)

    def close(self):
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

    def install_exception_hooks(self):
        """Log crashes nobody caught, in the main thread and in background threads."""
        crash_log = self.get("uncaught")

        def on_crash(exc_type, exc, tb):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc, tb)  # let Ctrl+C behave normally
                return
            crash_log.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

        def on_thread_crash(args):
            crash_log.critical("Uncaught exception in thread %s",
                               args.thread.name if args.thread else "?",
                               exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

        sys.excepthook = on_crash
        threading.excepthook = on_thread_crash

    # ---------- handing out loggers ----------

    def get(self, component):
        """Child logger for a name, a class, or an instance: get("crime"), get(MyClass), get(self)."""
        if isinstance(component, str):
            child = component
        elif isinstance(component, type):
            child = component.__name__
        else:
            child = type(component).__name__
        return self._logger.getChild(child)

    # ---------- convenience for main() ----------
    # stacklevel=2 makes log records show the caller's file/line, not this wrapper's.

    def debug(self, msg, *args):
        self._logger.debug(msg, *args, stacklevel=2)

    def info(self, msg, *args):
        self._logger.info(msg, *args, stacklevel=2)

    def warning(self, msg, *args):
        self._logger.warning(msg, *args, stacklevel=2)

    def error(self, msg, *args):
        self._logger.error(msg, *args, stacklevel=2)

    def exception(self, msg, *args):
        """Call inside an except block; logs at ERROR with the traceback."""
        self._logger.exception(msg, *args, stacklevel=2)