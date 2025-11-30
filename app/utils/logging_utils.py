import logging

def mask_key(key: str) -> str:
    """
    Mask an API key, showing only the last 4 characters.
    If key is None or empty, returns 'None'.
    """
    if not key:
        return "None"
    if len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
