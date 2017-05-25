import time

import utils
import teamworker
import shopifier


def log(s):
    print(f'{utils.time_str()}: {s}')

utils.mkdirs()

while True:
    tw = None
    try:
        log('Run Teamworker')
        tw = teamworker.Teamwork2Shopify()
        tw.init_tw()
        tw.import_styles()
        tw.import_rta_by_date()
    except Exception as e:
        log(e)
    finally:
        if tw and tw.db:
            try:
                tw.db.close()
            except Exception:
                pass

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

    log('Sleep for 5 minutes\n')
    time.sleep(300)
