import datetime
import logging
import sys
import os, shutil

_DIR = 'tw2sf'

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler(f'{name}.log', mode='w')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger


def time_str():
    return datetime.datetime.now().strftime('%Y%m%d-%H%M%S.%f')[:-3]


def mkdirs(clean=False):
    if clean and os.path.exists(_DIR):
        shutil.rmtree(_DIR)
    for dir in ['log','xml']:
        dir = os.path.join(_DIR, dir)
        if not os.path.exists(dir):
            os.makedirs(dir)
