import logging
import logging.config
import datetime


def beijing_time_converter(timestamp):
    """将时间转换为北京时间"""
    utc_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    beijing_dt = utc_dt.astimezone(beijing_tz)
    return beijing_dt.timetuple()


LEVEL_TAGS = {
    "DEBUG": "[D]",
    "INFO": "[I]",
    "WARNING": "[W]",
    "ERROR": "[E]",
    "CRITICAL": "[C]",
}


class AlignedFormatter(logging.Formatter):
    """将日志级别显示为固定 3 字符短标签（[W]/[I]/[E]...），保证 emoji 列对齐"""

    def format(self, record):
        record.levelname = LEVEL_TAGS.get(record.levelname, f"[{record.levelname[0]}]")
        return super().format(record)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "()": "logging_config.AlignedFormatter",
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


def init_logger():
    """初始化日志"""
    logging.Formatter.converter = staticmethod(beijing_time_converter)
    logging.config.dictConfig(LOGGING_CONFIG)
    return logging.getLogger()
