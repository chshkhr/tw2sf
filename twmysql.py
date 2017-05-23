import pymysql # sudo python3.6 -m pip install pymysql

_HOST = [
         '95.47.116.157',
         'localhost',
        ]
_PORT = [
         33063,
         3306
        ]
_USER = 'teamwork'
_PASSWORD = 'teamwork123'
_DB = 'teamwork'


def get_db(cursorclass=pymysql.cursors.DictCursor,autocommit=True):
    db = None
    i = 0
    while i < len(_HOST):
        try:
            db = pymysql.connect(host=_HOST[i],
                                 port=_PORT[i],
                                 user=_USER,
                                 password=_PASSWORD,
                                 db=_DB,
                                 charset='utf8mb4',
                                 cursorclass=cursorclass)
        except Exception as e:
            print(f"\tCan't connect to {_HOST[i]}:{_PORT[i]}")
        else:
            # print(f'\tConnected to {_HOST[i]}:{_PORT[i]}')
            break
        finally:
            i += 1

    db.autocommit(autocommit)
    return db
