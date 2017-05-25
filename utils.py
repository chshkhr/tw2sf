import datetime
import os, shutil

_DIR = 'tw2sf'


def time_str():
    return datetime.datetime.now().strftime('%Y%m%d-%H%M%S.%f')[:-3]


def mkdirs(clean=False):
    if clean and os.path.exists(_DIR):
        shutil.rmtree(_DIR)
    for dir in ['log','xml']:
        dir = os.path.join(_DIR, dir)
        if not os.path.exists(dir):
            os.makedirs(dir)
