import pymysql # sudo python3.6 -m pip install pymysql

from sys import platform
if platform == 'linux' or platform == 'linux2':
    _HOST = 'localhost'
    _PORT = 3306
else:
    _HOST = '95.47.116.157'
    _PORT = 33063

_USER = 'teamwork'
_PASSWORD = 'teamwork123'
_DB = 'teamwork'


def get_db(cursorclass=pymysql.cursors.DictCursor):
    db = None
    try:
        db = pymysql.connect(host=_HOST,
                             port=_PORT,
                             user=_USER,
                             password=_PASSWORD,
                             db=_DB,
                             charset='utf8mb4',
                             cursorclass=cursorclass)
        db.autocommit(True)
        print(f"\tConnected to {_HOST}:{_PORT}")
    except Exception as e:
        print(f"\tCan't connect to {_HOST}:{_PORT}")
    return db
