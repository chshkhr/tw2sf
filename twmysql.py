import pymysql # sudo python3.6 -m pip install pymysql

from sys import platform
if platform == 'linux' or platform == 'linux2':
    HOST = 'localhost'
    PORT = 3306
else:
    HOST = '95.47.116.157'
    PORT = 33063

DB = 'teamwork'
_USER = 'teamwork'
_PASSWORD = 'teamwork123'


def get_db(cursorclass=pymysql.cursors.DictCursor):
    db = None
    try:
        db = pymysql.connect(host=HOST,
                             port=PORT,
                             user=_USER,
                             password=_PASSWORD,
                             db=DB,
                             charset='utf8mb4',
                             cursorclass=cursorclass)
        db.autocommit(True)
        # print(f'\tConnected to "{HOST}:{PORT} {DB}"')
    except Exception as e:
        print(f'\tCan\'t connect to "{HOST}:{PORT} {DB}": {e}')
    return db
