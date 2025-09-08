import logging

import dataset
from .conf import get_config
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool


def load_derivers(database,user,password,host,port):
    # 尝试不同的MySQL驱动
    drivers = [
        "mysql+pymysql",  # PyMySQL
        "mysql+mysqldb",  # MySQLdb
        "mysql+mysqlconnector"  # MySQL Connector
    ]
    for driver in drivers:
        db_url = f"{driver}://{user}:{password}@{host}:{port}/{database}"
        dataset.connect(db_url).close()
        logging.info(f"MySQL 使用驱动: {driver}")
        return db_url
    raise Exception("没有可用的MySQL驱动，请安装 PyMySQL、mysqlclient 或 mysql-connector-python")


def _conn_mysql():
    database = get_config('mysql', {}).get('database')
    user = get_config('mysql', {}).get('user')
    password = get_config('mysql', {}).get('password')
    host = get_config('mysql', {}).get('host')
    port = get_config('mysql', {}).get('port')

    # 构建数据库连接URL
    # 格式: mysql://username:password@host:port/database_name
    db_url = load_derivers(database,user,password,host,port)
    return dataset.connect(db_url)
@contextmanager
def get_conn():
    db = None
    try:
        db = _conn_mysql()
        yield db
    finally:
        if db:
            db.close()


def _create_db_pool():
    database = get_config('mysql', {}).get('database')
    user = get_config('mysql', {}).get('user')
    password = get_config('mysql', {}).get('password')
    host = get_config('mysql', {}).get('host')
    port = get_config('mysql', {}).get('port')
    # 构建数据库连接URL
    # 格式: mysql://username:password@host:port/database_name
    db_url = load_derivers(database,user,password,host,port)
    # 创建带连接池的引擎
    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=100,  # 连接池大小
        max_overflow=200,  # 最大溢出连接数
        pool_pre_ping=False,  # 连接前测试有效性
        pool_recycle=3600  # 连接回收时间(秒)
    )
    logging.info(f"engine: {engine}")
    return engine


# 全局连接池实例
_db_pool = _create_db_pool()

@contextmanager
def get_pool_conn():
    """从连接池获取连接的上下文管理器"""
    engine = _db_pool
    db = None
    try:
        # 从连接池获取连接
        db = dataset.connect(str(engine.url))
        yield db
    except Exception as e:
        if db:
            db.rollback()
        raise
    finally:
        # 连接自动返回连接池
        if db:
            db.close()
