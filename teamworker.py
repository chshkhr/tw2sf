import re
import os
import glob
import time
import argparse
import datetime
import dateutil.parser # sudo python3.6 -m pip install python-dateutil
import requests # sudo python3.6 -m pip install requests
import xml.etree.ElementTree as ET

import twmysql
import utils

# Teamwork
TW_API_KEY = '9CA9E29D-D258-48DC-886E-A507F55A03D6'
TW_URL = 'https://hattestchq.teamworkinsight.com/'

# Global
start_date = dateutil.parser.parse('2017-01-24 00:00:00')  # (persistent)
shift_ms = 3  # set 3 at minimum to avoid repeatable sending of the last record
start_date_ = None  # start_date_ = start_date + shift_ms
chunk_size = 100  # Number of records per one request
chunk_num = 0  # Current chunk number

apiDocumentId = None
syncRunsID = None
db = None


def save_xml(r):
    # Saving XML Response content to file
    fn = os.path.join(utils._DIR, 'xml', utils.time_str()+'.xml')
    print('\tSaving Response to', fn, '...')
    with open(fn, 'bw') as f:
        f.write(r.content)


def get_root(r):
    # Get Root from XML Response, removing All XML NameSpaces
    s = re.sub(r'\sxmlns="[^\"]+"', '', r.content.decode('utf-8'), flags=re.MULTILINE)
    return ET.fromstring(s)


def request_styles(req):
    # Get XML from Teamwork and Save to MySqL
    global chunk_num, apiDocumentId, syncRunsID, start_date, start_date_
    global db
    chunk_num += 1
    done = 0
    print(f'Requesting Styles modified from {start_date_}. Chunk #{chunk_num}...')
    data = {'Data': req,
            'Source': 'VC_Test', 'UseApiVersion2': 'true',
            'ApiKey': TW_API_KEY, 'Async': 'true',
            'ApiRequestType': 'inventory-export'}
    r = requests.post(TW_URL + 'api.ashx', data=data)

    # Get XML from Teamwork
    root = get_root(r)
    a = root.attrib['ApiDocumentId']
    status = root.attrib['Status']
    while status == 'InProcess':
        time.sleep(5)
        r = requests.post(TW_URL + 'ApiStatus.ashx', data={'ID': a})
        root = get_root(r)
        status = root.attrib['Status']
    save_xml(r)

    with db.cursor() as cursor:
        if not apiDocumentId:
            apiDocumentId = a
            cursor.execute('INSERT INTO SyncRuns (ApiDocumentId) VALUES (%s)',(apiDocumentId,))
            cursor.execute('SELECT LAST_INSERT_ID() as SyncRunsID')
            data = cursor.fetchone()
            syncRunsID = data['SyncRunsID']

        # Copy Styles to Items
        for style in root.iter('Style'):
            try:
                title = style.find('Description4').text
                start_date = style.find('RecModified').text  # next time we'll start from this date
                styleno = style.find('StyleNo').text
                print('\t', done, start_date, styleno, title)
                cursor.execute("INSERT INTO Styles (SyncRunsID, StyleNo, RecModified, Title, StyleXml)"+
                               " VALUES (%s, %s, %s, %s, %s)",
                               (syncRunsID, styleno, start_date, title, ET.tostring(style), ))
            except Exception as e:
                print('\t\t', e)
            finally:
                done += 1
        print(f'\t{done} Styles found in the last Response and saved to DB {twmysql._DB}')
        cursor.execute('UPDATE SyncRuns SET '
                       'StylesFound = StylesFound + %s, '
                       'LastChunkTime = CURRENT_TIMESTAMP(3), '
                       'ChunkCount = ChunkCount + 1 '
                       'where ID = %s;',
                       (done,syncRunsID))

    return done


def init(drop=False):
    global start_date, start_date_, db
    global apiDocumentId

    utils.mkdirs()

    # MySql Init
    db = twmysql.get_db()

    if drop:
        with db.cursor() as cursor:
            for t in ['Styles','SyncRuns']:
                sql = f'DROP TABLE IF EXISTS {t};'
                print(sql)
                cursor.execute(sql)

    with db.cursor() as cursor:
        # Execute SQL scripts from .\SQL folder (if SyncRuns table not found in DB)
        if not cursor.execute("SHOW TABLES LIKE 'SyncRuns'"):
            for fn in glob.glob(os.path.join('sql','*.sql')):
                print(f'Executing {fn}...')
                with open(fn,'br') as f:
                        for sql in f.read().decode('utf-8').split('\r\n\r\n'):
                            sql = sql.strip()
                            if sql:
                                cursor.execute(sql)

        # We are starting from the modification time of the last received record
        cursor.execute('select max(RecModified) as startdate from Styles;')
        data = cursor.fetchone()
        if data['startdate']:
            start_date = data['startdate']
            if shift_ms:
                start_date += datetime.timedelta(milliseconds=shift_ms)
        start_date_ = start_date.isoformat(timespec='milliseconds')


def run():
    global start_date_, apiDocumentId, chunk_size, chunk_num
    apiDocumentId = None
    chunk_num = 0
    # Main Loop
    done = request_styles('<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                          'xmlns="http://microsoft.com/wsdl/types/">'
                          '<Request>'
                          '<Filters>'
                          '<Filter Field="RecModified" Operator="Greater than or equal" '
                          f'Value="{start_date_}" />'
                          '</Filters>'
                          '<SortDescriptions>'
                          '<SortDescription Name="RecModified" Direction="Ascending" />'
                          '</SortDescriptions>'
                          f'<Top>{chunk_size}</Top>'
                          '</Request>'
                          '</ApiDocument>')
    skip = done
    while done > 0:
        done = request_styles(f'<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                              'xmlns="http://microsoft.com/wsdl/types/">'
                              '<Request>'
                              f'<ParentApiDocumentId>{apiDocumentId}</ParentApiDocumentId>'
                              f'<Top>{chunk_size}</Top>'
                              f'<Skip>{skip}</Skip>'
                              '</Request>'
                              '</ApiDocument>')
        skip += done


if __name__ == '__main__':
    try:
        # Command line arguments processing
        parser = argparse.ArgumentParser(description=f'Getting Teamwork Inventory from {TW_URL}')
        parser.add_argument('--chunk', type=int, help=f'Chunk Size ({chunk_size})')
        parser.add_argument('--start', help=f'Start Date ({start_date})')
        parser.add_argument('--drop', nargs='?', type=bool, const=False,
                            help=f'Drop tables in {twmysql._DB}')
        args = parser.parse_args()
        if args.chunk is not None:
            chunk_size = int(args.chunk)
        if args.start is not None:
            start_date = args.start

        init(args.drop)

        run()

    finally:
        db.close()