import logging
import os
import yaml

SERVICE_CONF = "conf/server.yaml"

PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir
            )
)

def load_config():
    conf_path = os.path.join(PROJECT_BASE, SERVICE_CONF)
    logging.info(f'加载配置文件路径{conf_path}')
    if os.path.exists(conf_path):
        with open(conf_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            return config
    else:
        raise FileNotFoundError(f"配置文件 {SERVICE_CONF} 不存在")


CONFIGS = load_config()

def show_config():
    for k, v in CONFIGS.items():
        if isinstance(v, dict):
            logging.info(f"{k}: {v}")

def get_config(key, default=None):
    if key is None:
        return None
    if default is None:
        default = os.environ.get(key.upper())
    return CONFIGS.get(key, default)