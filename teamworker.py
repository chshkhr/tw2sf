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
TW_API_KEY = '4f684ea6-f949-42d0-837b-7eaabf10ae03'  # '9CA9E29D-D258-48DC-886E-A507F55A03D6'
TW_URL = 'https://qa03chq.teamworkinsight.com/'  # 'https://hattestchq.teamworkinsight.com/'

# Global
start_date = dateutil.parser.parse('2017-01-24 00:00:00')  # used on first run, get from DB later
shift_ms = 3  # set 3 at minimum to avoid repeatable sending of the last record
start_date_ = None  # start_date_ = start_date + shift_ms
chunk_size = 100  # Number of records per one request
chunk_num = 0  # Current chunk number
skip = 0
max_wait = 60  # Max waiting time for Successfull status (seconds)

apiDocumentId = None
syncRunsID = None
db = None
last_response = None


def save_xml(r):
    # Saving XML Response content to file
    if r:
        try:
            fn = os.path.join(utils._DIR, 'xml', utils.time_str()+'.xml')
            print('\tSaving Response to', fn, '...')
            with open(fn, 'bw') as f:
                f.write(r.content)
        except:
            pass


def get_root_from_response(response):
    # Get Root from XML Response, removing All XML NameSpaces
    s = re.sub(r'\sxmlns="[^\"]+"', '', response.content.decode('utf-8'), flags=re.MULTILINE)
    return ET.fromstring(s)


def get_xml_root(req, apitype):
    # Get XML by api-type
    global apiDocumentId, last_response
    xml_root = None
    last_response = None
    try:
        data = {'Data': req,
                'Source': 'VC_Test', 'UseApiVersion2': 'true',
                'ApiKey': TW_API_KEY, 'Async': 'true',
                'ApiRequestType': apitype}
        last_response = requests.post(TW_URL + 'api.ashx', data=data)
        xml_root = get_root_from_response(last_response)
        a = xml_root.attrib['ApiDocumentId']
        status = xml_root.attrib['Status']
        count = 0
        wait = 3
        while status == 'InProcess':
            time.sleep(wait)
            last_response = requests.post(TW_URL + 'ApiStatus.ashx', data={'ID': a})
            xml_root = get_root_from_response(last_response)
            status = xml_root.attrib['Status']
            count += 1
            if count > max_wait // wait:
                break
        if status == 'Successful':
            apiDocumentId = a  # None otherwise
    except (KeyboardInterrupt, SystemExit) as e:
        db = None
        return None
    else:
        return xml_root


def import_styles_chunk(req):
    # Get XML from Teamwork and Save to MySqL
    global chunk_num, skip, apiDocumentId, syncRunsID, start_date, start_date_
    global db, last_response
    chunk_num += 1
    done = 0

    print(f'\tRequesting Styles modified from {start_date_}. Chunk #{chunk_num}...')

    # Get syncRunsID of not finished session or create the new one
    if chunk_num == 1:  # means First Run
        with db.cursor() as cursor:
            cursor.execute('SELECT Max(ID) as SyncRunsID FROM SyncRuns')
            data = cursor.fetchone()
            syncRunsID = data['SyncRunsID']
            if syncRunsID is not None:
                cursor.execute('SELECT StylesFound, SessionFinishTime FROM SyncRuns WHERE ID=%s', (syncRunsID,))
                data = cursor.fetchone()
            if syncRunsID is None or data['StylesFound'] > 0 or data['SessionFinishTime'] is None:
                # 'SessionFinishTime is Null' means simultaneous executions or interrupted process (we keep this info)
                cursor.execute('INSERT INTO SyncRuns (ApiDocumentId) VALUES (Null)')
                cursor.execute('SELECT LAST_INSERT_ID() as SyncRunsID')
                data = cursor.fetchone()
                syncRunsID = data['SyncRunsID']

    # Get Style XML from Teamwork
    xml_root = get_xml_root(req, 'inventory-export')

    if db and xml_root and apiDocumentId:
        try:
            with db.cursor() as cursor:
                # Write Starting Time on First run
                if chunk_num == 1:
                    cursor.execute('SELECT Max(ID) as SyncRunsID FROM SyncRuns')
                    data = cursor.fetchone()
                    syncRunsID = data['SyncRunsID']
                    cursor.execute('UPDATE SyncRuns SET '
                                   'SessionNum = SessionNum + 1, '
                                   'ApiDocumentId = %s, ' 
                                   'SessionStartTime = CURRENT_TIMESTAMP(3), '
                                   'SessionFinishTime = Null '
                                   'WHERE ID = %s',
                                   (apiDocumentId,
                                    syncRunsID,))

                # Copy Styles to Items
                for style in xml_root.iter('Style'):
                    try:
                        title = style.find('CustomText5').text or style.find('Description4').text
                        start_date = style.find('RecModified').text  # next time we'll start from this date
                        styleno = style.find('StyleNo').text
                        print('\t\t', skip+done+1, start_date, styleno, title)
                        cursor.execute("INSERT INTO StyleStream (SyncRunsID, StyleNo, StyleId, RecModified, Title, StyleXml)"+
                                       " VALUES (%s, %s, %s, %s, %s, %s)",
                                       (syncRunsID, styleno, style.find('StyleId').text, start_date, title, ET.tostring(style), ))
                    except Exception as e:
                        print('\t\t\t', e)
                    finally:
                        done += 1
                print(f'\t{done} Styles found in the last Response and saved to DB {twmysql._DB}')

                # Write current time and counters on each run
                cursor.execute('UPDATE SyncRuns SET '                      
                               'SessionFinishTime = case when %s = 0 then CURRENT_TIMESTAMP(3) else SessionFinishTime end, '
                               'StylesFound = StylesFound + %s, '
                               'ChunkCount = ChunkCount + %s, '
                               'LastChunkTime = case when %s > 0 then CURRENT_TIMESTAMP(3) else LastChunkTime end '
                               'where ID = %s;',
                               (int(done > 0),
                                done,
                                int(done > 0),
                                done,
                                syncRunsID,
                                ))
        except (KeyboardInterrupt, SystemExit) as e:
            db = None
        finally:
            if done:
                save_xml(last_response)

    return done


def init(drop=False):
    global start_date, start_date_, db
    global apiDocumentId

    utils.mkdirs(drop)

    # MySql Init
    db = twmysql.get_db()

    if drop:
        with db.cursor() as cursor:
            for t in ['Items', 'Styles', 'StyleStream', 'SyncRuns']:
                sql = f'DROP TABLE IF EXISTS {t};'
                print('\t', sql)
                cursor.execute(sql)

    with db.cursor() as cursor:
        # Execute SQL scripts from .\SQL folder (if SyncRuns table not found in DB)
        if not cursor.execute("SHOW TABLES LIKE 'SyncRuns'"):
            for fn in sorted(glob.glob(os.path.join('sql','*.sql'))):
                print(f'\tExecuting {fn}...')
                with open(fn,'br') as f:
                        for sql in f.read().decode('utf-8').split('\r\n\r\n'):
                            sql = sql.strip()
                            if sql:
                                cursor.execute(sql)

        # We are starting from the modification time of the last received record
        cursor.execute('select max(RecModified) as startdate from StyleStream;')
        data = cursor.fetchone()
        if data['startdate']:
            start_date = data['startdate']
            if shift_ms:
                start_date += datetime.timedelta(milliseconds=shift_ms)
        start_date_ = start_date.isoformat(timespec='milliseconds')


def import_styles():
    global start_date_, apiDocumentId, chunk_size, chunk_num, skip
    apiDocumentId = None
    chunk_num = 0
    # Main Loop
    done = import_styles_chunk('<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
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
    if apiDocumentId is None:
        print("\tCan't get 'Successful' Status from Server!")
    else:
        skip = done
        while db and done > 0:
            done = import_styles_chunk(f'<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
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

        import_styles()

    finally:
        if db:
            db.close()