from logging import Formatter, Logger
from logging.handlers import RotatingFileHandler

from redis import Redis

from rest.core.hive_config import HiveConfig

class Aggregator:
    def __init__(self) -> None:
        super().__init__()

    def close(self) -> None:
        pass

    def commit(self, values: dict, name: str) -> None:
        pass


class DataCollector(Aggregator):
    def __init__(self) -> None:
        super().__init__()
        self.__aggregators = list()

    def add_aggregator(self, aggregator: Aggregator) -> None:
        self.__aggregators.append(aggregator)

    def remove_aggregator(self, aggregator: Aggregator) -> None:
        self.__aggregators.remove(aggregator)

    def close(self) -> None:
        for a in self.__aggregators:
            a.close()

    def commit(self, values: dict, name: str) -> None:
        for a in self.__aggregators:
            a.commit(values, name)


class ConsoleAggregator(Aggregator):
    MAX_BYTES = int(1.5 * 1024 * 1024)  # ~1.5MB
    FORMAT = '%(levelname)s: %(asctime)s - %(message)s'
    DATE_FORMAT = '%d.%m.%Y %H:%M:%S'

    def __init__(self, base_path: str) -> None:
        super().__init__()
        self.__base_path = base_path
        self.__loggers = dict()

    def __init_logger(self, name: str) -> None:
        logger = Logger(name)
        handler = RotatingFileHandler(self.__base_path + name + '.log', maxBytes=self.MAX_BYTES, backupCount=1)
        formatter = Formatter(self.FORMAT, datefmt=self.DATE_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        self.__loggers[name] = logger

    def close(self) -> None:
        for v in self.__loggers.values():
            for h in v.handlers:
                h.flush()
                h.close()

    def commit(self, values: dict, name: str) -> None:
        if name not in self.__loggers:
            self.__init_logger(name)
        logger = self.__loggers[name]
        logger.info(values)


class RedisAggregator(Aggregator):
    def __init__(self) -> None:
        super().__init__()
        url, port = HiveConfig().get_database_data()
        self.__redis = Redis(host=url, port=port, db=0)

    def close(self) -> None:
        super().close()

    def commit(self, values: dict, name: str) -> None:
        self.__redis.set(name + '@' + str(values['timestamp']), str(values))
