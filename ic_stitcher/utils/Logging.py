import logging
import json
import getpass
import logging.handlers
from pathlib import Path

class _JSONLogger():
    """Log information in JSON format, categorized by errors, warnings, infos
    """
    def __init__(self) -> None:
        self.error = []
        self.warning = []
        self.info = []
        self.user = getpass.getuser()
    
    def add(self, msg, level) -> None:
        if(level == logging.ERROR or 
           level == logging.CRITICAL):
            self.error.append(msg)
        elif(level == logging.WARNING):
            self.warning.append(msg)
        else:
            self.info.append(msg)
    
    def save(self, file:str):
        data = {
            'user': self.user,
            'ERROR': self.error,
            'WARNING': self.warning,
            'INFO': self.info
        }
        Path(file).write_text(json.dumps(data,indent=4))

_default_format = "| %(asctime)s | %(levelname)s [%(name)s]: %(message)s "
LOGGER = None
TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
# Global Logger for accumulation all log-info 
JSONLOG = _JSONLogger()

class _CustomFormatter(logging.Formatter):
    """ Colored logging class for formatting log output """
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = _default_format
    extend_format = format + "( %(filename)s:%(lineno)d )"
    FORMATS = {
        logging.NOTSET: grey + format + reset,
        logging.DEBUG: grey + extend_format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + extend_format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, TIME_FORMAT)
        formatted = formatter.format(record)
        return formatted

class _JSONLogHandler(logging.Handler):
    """ Just store a message in JSONLOG"""
    def emit(self, record) -> None:
        formatted_json = self.formatter.format(record)
        JSONLOG.add(formatted_json, record.levelno)

def addStreamHandler( logger: logging.Logger) -> None:
    #logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    ch.setFormatter(_CustomFormatter())    
    # add the handlers to logger
    logger.addHandler(ch)
    
def addFHLogger( logger: logging.Logger,
                log_file: str,
                max_bytes = 1e7,
                file_count = 5,
                override: bool = False) -> None:
    """ Add a file handler to the existing _logger, so the logger additionaly writes a log into a _log_file. 
        If _is_quite = True, it sets the logging level to ERROR, preventing unnecessary messages to be printed out.
    """
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler) and handler.baseFilename == str(Path(log_file).resolve()): # If file in handlers
            return None
    if(override):
        mode = 'w'
    else:
        mode = 'a'
    fh = logging.handlers.RotatingFileHandler(log_file, mode=mode, maxBytes=max_bytes, backupCount=file_count)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_default_format)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
def addJSONLogger( logger: logging.Logger) -> None:
    """ Add a JSON file handler to the existing _logger, so the logger additionaly writes a log into a _log_file. 
        If _is_quite = True, it sets the logging level to ERROR, preventing unnecessary messages to be printed out.
    """
    # JSON Handler
    jsonh = _JSONLogHandler()
    jsonh.setLevel(logging.DEBUG)
    jsonh.setFormatter(logging.Formatter("%(asctime)s [%(name)s]: %(message)s", TIME_FORMAT))
    logger.addHandler(jsonh)
    