import pymysql # sudo python3.6 -m pip install pymysql

_HOST = '95.47.116.157'
_PORT = 33063
_USER = 'teamwork'
_PASSWORD = 'teamwork123'
_PASSWORD = 'teamwork123'
_DB = 'teamwork'


def get_db(cursorclass=pymysql.cursors.DictCursor,autocommit=True):
    db = pymysql.connect(host=_HOST,
                         port=_PORT,
                         user=_USER,
                         password=_PASSWORD,
                         db=_DB,
                         charset='utf8mb4',
                         cursorclass=cursorclass)
    db.autocommit(autocommit)
    return db
