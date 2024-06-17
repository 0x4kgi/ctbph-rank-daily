import logging

def setup_logging(
    level: int = logging.INFO,
) -> logging.Logger:
    # Assisited by ChatGPT(tm)

    logger = logging.getLogger(name='ctbph-rank-daily')
    logger.setLevel(level=level)

    # Create handlers
    # tbh i dont really know why
    ch = logging.StreamHandler()
    ch.setLevel(level=level)

    # Create formatters and add them to handlers
    # https://docs.python.org/3/library/logging.html#formatter-objects
    # https://docs.python.org/3/library/logging.html#logrecord-attributes
    formatter = logging.Formatter(
        # fmt='[{levelname:<7}] {message} ({filename}:{lineno}:{funcName})',
        fmt='{filename}:{lineno}\t- {levelname:<8} - {message}',
        style='{'
    )
    ch.setFormatter(fmt=formatter)

    # Add handlers to the logger
    logger.handlers = []  # Clear existing handlers
    logger.addHandler(ch)

    return logger

logger = setup_logging()