import logging

# messes with the logs in the file but i kinda dont care anymore
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[0;37m',    # White
        'INFO': '\033[0;36m',     # Cyan
        'WARNING': '\033[0;33m',  # Yellow
        'ERROR': '\033[0;31m',    # Red
        'CRITICAL': '\033[0;35m'  # Magenta
    }

    RESET = '\033[0m'  # Reset to default

    def format(self, record):
        loglevel_color = self.COLORS.get(record.levelname, self.RESET)
        
        # https://docs.python.org/3/library/logging.html#logging.LogRecord
        record.levelname = f'{loglevel_color} {record.levelname.ljust(8)} {self.RESET}'
        record.msg = f'{loglevel_color}{record.msg}{self.RESET}'
        
        return super().format(record)

def setup_logging(
    level: int = logging.INFO,
) -> logging.Logger:
    # Assisited by ChatGPT(tm)

    # this is for file logging
    logging.basicConfig(
        filename='tests/log.log',
        format='{asctime} {levelname:<8} {name} {filename}:{lineno} - {message} "@{funcName}"',
        style='{',
    )

    logger = logging.getLogger(name='ctbph-rank-daily')
    logger.setLevel(level=level)

    # Create handlers
    ch = logging.StreamHandler()
    ch.setLevel(level=level)

    # Create formatters and add them to handlers
    # https://docs.python.org/3/library/logging.html#formatter-objects
    # https://docs.python.org/3/library/logging.html#logrecord-attributes
    # https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal
    formatter = ColoredFormatter(
        fmt='{levelname:<8} - {filename}:{lineno}\t\t - {message} \033[90m({funcName})\033[0m',
        style='{'
    )
    ch.setFormatter(fmt=formatter)

    # Add handlers to the logger
    logger.handlers = []  # Clear existing handlers
    logger.addHandler(ch)

    return logger

logger = setup_logging()