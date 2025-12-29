# [2025-12-29] infrastructure/transport/factory.py
import socket
import time
from abc import ABC, abstractmethod
from typing import Optional

# --- Base Interfaces ---
class BaseProducer(ABC):
    @abstractmethod
    def start(self): pass
    @abstractmethod
    def publish(self, topic: str, payload: bytes): pass
    @abstractmethod
    def stop(self): pass

class BaseConsumer(ABC):
    @abstractmethod
    def start(self): pass
    @abstractmethod
    def poll(self, timeout: float = 1.0) -> Optional[bytes]: pass
    @abstractmethod
    def stop(self): pass

# --- SimpleBus Implementation ---
class SimpleBusProducer(BaseProducer):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"[Transport] Producer connected to SimpleBus at {self.host}:{self.port}")
        except Exception as e:
            print(f"[Transport] Producer connection failed: {e}")
            raise

    def publish(self, topic: str, payload: bytes):
        if not self.sock: return
        try:
            self.sock.sendall(payload + b'\n')
        except Exception as e:
            print(f"[Transport] Send failed: {e}")
            self.sock.close()
            self.sock = None

    def stop(self):
        if self.sock: self.sock.close()

class SimpleBusConsumer(BaseConsumer):
    def __init__(self, host: str, port: int, topic: str):
        self.host = host
        self.port = port
        self.topic = topic
        self.sock = None
        self.buffer = b""

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1.0)
            self.sock.connect((self.host, self.port))
            print(f"[Transport] Consumer connected to SimpleBus at {self.host}:{self.port}")
        except Exception as e:
            print(f"[Transport] Consumer connection failed: {e}")
            raise

    def poll(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self.sock: return None
        if b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            return line
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(4096)
            if not data:
                self.sock.close(); self.sock = None; return None
            self.buffer += data
            if b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                return line
            else: return None
        except socket.timeout: return None
        except Exception as e:
            print(f"[Transport] Recv error: {e}")
            self.sock.close(); self.sock = None; return None

    def stop(self):
        if self.sock: self.sock.close()

# --- Kafka Implementation ---
try:
    from confluent_kafka import Producer, Consumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

class KafkaProducerAdapter(BaseProducer):
    def __init__(self, brokers: str, client_id: str = "v1-producer"):
        if not KAFKA_AVAILABLE: raise ImportError("confluent-kafka library is missing")
        self.brokers = brokers
        self.client_id = client_id
        self.producer = None

    def start(self):
        conf = {'bootstrap.servers': self.brokers, 'client.id': self.client_id, 'acks': '1', 'retries': 0}
        self.producer = Producer(conf)
        print(f"[Transport] Kafka Producer connected to {self.brokers}")

    def publish(self, topic: str, payload: bytes):
        if not self.producer: return
        try:
            self.producer.produce(topic, payload)
            self.producer.poll(0)
        except Exception as e: print(f"[Transport] Kafka Error: {e}")

    def stop(self):
        if self.producer: self.producer.flush()

class KafkaConsumerAdapter(BaseConsumer):
    def __init__(self, brokers: str, group_id: str, topics: list):
        if not KAFKA_AVAILABLE: raise ImportError("confluent-kafka library is missing")
        self.brokers = brokers
        self.group_id = group_id
        self.topics = topics
        self.consumer = None

    def start(self):
        conf = {'bootstrap.servers': self.brokers, 'group.id': self.group_id, 'auto.offset.reset': 'latest', 'enable.auto.commit': True}
        self.consumer = Consumer(conf)
        self.consumer.subscribe(self.topics)
        print(f"[Transport] Kafka Consumer joined group {self.group_id}")

    def poll(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self.consumer: return None
        try:
            msg = self.consumer.poll(timeout)
            if msg is None: return None
            if msg.error(): return None
            return msg.value()
        except Exception: return None

    def stop(self):
        if self.consumer: self.consumer.close()

# --- Factory ---
class TransportFactory:
    @staticmethod
    def create_producer(type: str, config: dict) -> BaseProducer:
        if type == "simple":
            return SimpleBusProducer(config['host'], int(config['port']))
        elif type == "kafka":
            return KafkaProducerAdapter(config['brokers'], client_id=config.get('client_id', 'v1-producer'))
        else:
            raise ValueError(f"Unknown transport type: {type}")

    @staticmethod
    def create_consumer(type: str, config: dict) -> BaseConsumer:
        if type == "simple":
            return SimpleBusConsumer(config['host'], int(config['port']), config.get('topic', ''))
        elif type == "kafka":
            return KafkaConsumerAdapter(config['brokers'], config['group_id'], [config['topic']])
        else:
            raise ValueError(f"Unknown transport type: {type}")