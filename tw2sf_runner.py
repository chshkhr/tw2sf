import time
import os
import sys

import utils
import teamworker
import shopifier

utils.mkdirs()
fn = os.path.join(utils._DIR, 'log', utils.time_str() + '.log')
f = open(fn, 'w')
sys.stdout = f


def log(s):
    f.write(f'{utils.time_str()}: {s}\n')
    f.flush()

try:
    log('Init Teamworker')
    teamworker.init()

    log('Init Shopifier')
    shopifier.init()

    while True:
        log('Run Teamworker')
        teamworker.run()

        log('Run Shopifier')
        shopifier.run()

        log('Sleep for 5 minutes')
        time.sleep(300)

except Exception as e:
    log(e)
finally:
    log('SHUTTING DOWN')
    sys.stdout = sys.__stdout__
    f.close()
