import time

import utils
import teamworker
import shopifier


def log(s):
    print(f'{utils.time_str()}: {s}')

utils.mkdirs()

while True:
    try:
        log('Run Teamworker')
        teamworker.init_tw()
        teamworker.import_styles()
        teamworker.import_rta_by_date()
    except Exception as e:
        log(e)
    finally:
        if teamworker.db:
            try:
                teamworker.db.close()
            except Exception:
                pass
        else:
            break

    try:
        log('Run Shopifier')
        shopifier.init_sf()
        shopifier.export_styles()
        shopifier.export_qty()
    except Exception as e:
        log(e)
    finally:
        if shopifier.db:
            try:
                shopifier.db.close()
            except Exception:
                pass
        else:
            break

    log('Sleep for 5 minutes\n')
    time.sleep(300)
