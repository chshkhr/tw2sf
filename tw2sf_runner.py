import time

import utils
import teamworker
import shopifier


def log(s):
    print(f'{utils.time_str()}: {s}')

utils.mkdirs()

while True:
    try:
        log('Init Teamworker')
        teamworker.init_tw()
        log('Run Teamworker')
        teamworker.import_styles()
    except Exception as e:
        log(e)
    finally:
        try:
            teamworker.db.close()
        except Exception:
            pass

    try:
        log('Init Shopifier')
        shopifier.init_sf()
        log('Run Shopifier')
        shopifier.export_styles()
    except Exception as e:
        log(e)
    finally:
        try:
            shopifier.db.close()
        except Exception:
            pass

    log('Sleep for 5 minutes')
    time.sleep(300)
