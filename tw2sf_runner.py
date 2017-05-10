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

    while True:
        try:
            log('Init Teamworker')
            teamworker.init()
            log('Run Teamworker')
            teamworker.run()
        except Exception as e:
            log(e)
        finally:
            try:
                teamworker.db.close()
            except Exception:
                pass

        try:
            log('Init Shopifier')
            shopifier.init()
            log('Run Shopifier')
            shopifier.run()
        except Exception as e:
            log(e)
        finally:
            try:
                shopifier.db.close()
            except Exception:
                pass

        log('Sleep for 5 minutes')
        time.sleep(300)

except Exception as e:
    log(e)
finally:
    log('SHUTTING DOWN')
    sys.stdout = sys.__stdout__
    f.close()
