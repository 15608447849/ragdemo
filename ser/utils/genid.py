import time
import threading
from dataclasses import dataclass


@dataclass
class UniqueIDGenerator:
    """高性能唯一ID生成器"""
    prefix: str = "99"  # 2位指定编码
    max_sequence: int = 1000  # 1秒内最大序列数
    sequence_bits: int = 10  # 序列号位数 (2^10 = 1024 > 1000)

    def __post_init__(self):
        if len(self.prefix) != 2:
            raise ValueError("前缀必须是2位字符")
        if self.max_sequence >= (1 << self.sequence_bits):
            raise ValueError("序列位数不足")

        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _get_current_timestamp(self) -> int:
        """获取当前时间戳（毫秒级）"""
        return int(time.time() * 1000)

    def _wait_next_millisecond(self, last_timestamp: int) -> int:
        """等待到下一毫秒"""
        timestamp = self._get_current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_current_timestamp()
        return timestamp

    def generate_id(self) -> str:
        """生成20位唯一ID"""
        with self.lock:
            timestamp = self._get_current_timestamp()

            # 处理时钟回拨
            if timestamp < self.last_timestamp:
                raise Exception("时钟回拨异常")

            # 如果是同一毫秒，递增序列号
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & ((1 << self.sequence_bits) - 1)
                # 序列号溢出，等待下一毫秒
                if self.sequence == 0:
                    timestamp = self._wait_next_millisecond(self.last_timestamp)
            else:
                # 新的毫秒，重置序列号
                self.sequence = 0

            self.last_timestamp = timestamp

            # 组合ID：时间戳(13位) + 前缀(2位) + 序列号(5位) = 20位
            timestamp_str = str(timestamp)[-13:]  # 取13位时间戳
            sequence_str = str(self.sequence).zfill(5)  # 5位序列号

            return f"{timestamp_str}{self.prefix}{sequence_str}"


class IDGeneratorFactory:
    """ID生成器工厂"""
    _instances = {}

    @classmethod
    def get_generator(cls, prefix: str = "99") -> UniqueIDGenerator:
        """获取指定前缀的生成器实例"""
        if prefix not in cls._instances:
            cls._instances[prefix] = UniqueIDGenerator(prefix=prefix)
        return cls._instances[prefix]