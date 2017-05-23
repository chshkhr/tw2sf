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

# Teamwork constants
TW_API_KEY = '4f684ea6-f949-42d0-837b-7eaabf10ae03'  # '9CA9E29D-D258-48DC-886E-A507F55A03D6'
TW_URL = 'https://qa03chq.teamworkinsight.com/'  # 'https://hattestchq.teamworkinsight.com/'
TW_LOCATIONS = ['7A2151DB-EFC2-49BD-913B-66EEE0DF38C1',
                'CA2E5100-1853-419C-9661-F11D6CFC4FB1']  # for RTA

# Settings
start_date = dateutil.parser.parse('2000-01-01 00:00:00')  # used on first run, get from DB later
shift_ms = 3  # set 3 at minimum to avoid repeatable sending of the last record
chunk_size = 100  # Number of records per one request
chunk_num = 0  # Current chunk number
max_wait = 60  # Max waiting time for Successfull status (seconds)
need_save_responses = True

# Global
apiDocumentId = None
apiRequestTime = None
syncRunsID = None
db = None
last_response = None
skip = 0


def _save_last_response(suffix=''):
    # Saving XML Response content to file
    if need_save_responses and last_response:
        try:
            fn = os.path.join(utils._DIR, 'xml', utils.time_str()+suffix+str(chunk_num)+'.xml')
            print('\t\t\tSaving Response to', fn, '...')
            with open(fn, 'bw') as f:
                f.write(last_response.content)
        except:
            pass


def _get_root_from_response(response):
    # Get Root from XML Response, removing All XML NameSpaces
    s = re.sub(r'\sxmlns="[^\"]+"', '', response.content.decode('utf-8'), flags=re.MULTILINE)
    return ET.fromstring(s)


def _get_xml_root(req, apitype):
    # Get XML by api-type
    global apiDocumentId, apiRequestTime, last_response
    xml_root = None
    last_response = None
    try:
        data = {'Data': req,
                'Source': 'VC_Test', 'UseApiVersion2': 'true',
                'ApiKey': TW_API_KEY, 'Async': 'true',
                'ApiRequestType': apitype}
        last_response = requests.post(TW_URL + 'api.ashx', data=data)
        xml_root = _get_root_from_response(last_response)
        a = xml_root.attrib['ApiDocumentId']
        status = xml_root.attrib['Status']
        count = 0
        wait = 3
        while status == 'InProcess':
            time.sleep(wait)
            last_response = requests.post(TW_URL + 'ApiStatus.ashx', data={'ID': a})
            xml_root = _get_root_from_response(last_response)
            status = xml_root.attrib['Status']
            count += 1
            if count > max_wait // wait:
                break
        if apiDocumentId is None and status == 'Successful':
            apiDocumentId = a  # None otherwise
        if 'apiRequestTime' in xml_root.attrib:
            apiRequestTime = xml_root.attrib['apiRequestTime']
    except (KeyboardInterrupt, SystemExit) as e:
        db = None
        return None
    else:
        if status == 'Error':
            print('\t\t'+xml_root.attrib[status])
        return xml_root


def _process_styles_xml(xml_root):
    # Proces XML from Teamwork and Save results to MySqL DB
    global chunk_num, skip, apiDocumentId, syncRunsID
    global db, last_response
    done = 0

    # Get syncRunsID of not finished session or create the new one
    if chunk_num == 1:  # means First Run
        with db.cursor() as cursor:
            cursor.execute('SELECT Max(ID) as SyncRunsID FROM SyncRuns')
            data = cursor.fetchone()
            syncRunsID = data['SyncRunsID']
            if syncRunsID is not None:
                cursor.execute('SELECT StylesFound, SessionFinishTime FROM SyncRuns WHERE ID = %s',
                               (syncRunsID,))
                data = cursor.fetchone()
            if syncRunsID is None or data['StylesFound'] > 0 or data['SessionFinishTime'] is None:
                # 'SessionFinishTime is Null' means simultaneous executions or interrupted process (we keep this info)
                cursor.execute('INSERT INTO SyncRuns (ApiDocumentId) VALUES (Null)')
                cursor.execute('SELECT LAST_INSERT_ID() as SyncRunsID')
                data = cursor.fetchone()
                syncRunsID = data['SyncRunsID']


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
                        styleno = style.find('StyleNo').text
                        title = (style.find('CustomText5').text or
                                 style.find('Description4').text or
                                 styleno)

                        start_date = style.find('RecModified').text  # next time we'll start from this date (next request)
                        styleid = style.find('StyleId').text
                        print('\t\t\t', skip+done+1, start_date, styleno, styleid, title)

                        cursor.execute('INSERT IGNORE INTO Styles (StyleId) '
                                       'VALUES (%s) ',
                                       (styleid,))

                        items = style.iter('Item')
                        var_count = 0
                        for item in items:
                            var_count += 1
                            cursor.execute('INSERT IGNORE INTO Items (ItemId, StyleId) '
                                           'VALUES (%s, %s) ',
                                           (item.find('ItemId').text,
                                            styleid,))

                        cursor.execute('INSERT INTO StyleStream '
                                       '(SyncRunsID, StyleNo, StyleId, RecModified, Title, '
                                       'VariantsCount, StyleXml) '
                                       'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                       (syncRunsID, styleno, styleid, start_date, title,
                                        var_count, ET.tostring(style), ))

                    except Exception as e:
                        print('\t\t\t\t', e)
                    finally:
                        done += 1
                print(f'\t\t\tStyles received: {done}. Saved to DB "{twmysql._DB}"')

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
                _save_last_response('-styles')

    return done


def init_tw(drop=False):
    # prepare folders for log and xml
    utils.mkdirs(drop)

    # MySql Init
    global db
    db = twmysql.get_db()

    # if we want to start from scratch then we drop all of our tables
    if drop:
        with db.cursor() as cursor:
            for t in ['Items', 'Styles', 'StyleStream', 'SyncRuns']:
                sql = f'DROP TABLE IF EXISTS {t};'
                print('\t', sql)
                cursor.execute(sql)

    # Execute SQL scripts from .\SQL folder (if SyncRuns table not found in DB)
    with db.cursor() as cursor:
        if drop or not cursor.execute("SHOW TABLES LIKE 'SyncRuns'"):
            for fn in sorted(glob.glob(os.path.join('sql', '*.sql'))):
                print(f'\tExecuting {fn}...')
                with open(fn,'br') as f:
                        s = f.read().decode('utf-8')
                        delim = '\r\n\r\n'
                        if s.find(delim) == -1:
                            delim = '\n\n'
                        for sql in s.split(delim):
                            sql = sql.strip()
                            #print(sql)
                            if sql:
                                cursor.execute(sql)


_api_request_prefix = ('<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                      'xmlns="http://microsoft.com/wsdl/types/"><Request>')
_api_request_suffix = '</Request></ApiDocument>'


def _multi_chunk_import(api_req, api_type, process_xml_function, one_chunk=False):
    global apiDocumentId, apiRequestTime, chunk_size, chunk_num, skip
    apiDocumentId = None
    apiRequestTime = None
    chunk_num = 1
    skip = 0
    done = 0
    total_rec = '?'

    # Main Loop
    req = (_api_request_prefix +
           api_req +
           f'<Top>{chunk_size}</Top>' +
           _api_request_suffix)
    # print('\t\tSend API request:',req)
    xml_root = _get_xml_root(req, api_type)
    if apiDocumentId is None:
        print("\tCan't get 'Successful' Status from Server!")
    else:
        if 'TotalRecords' in xml_root.attrib:
            total_rec = int(xml_root.attrib['TotalRecords'])
            if not one_chunk:
                print(f'\t\tChunk #{chunk_num} {skip}/{total_rec}...')
        if process_xml_function:
            done = process_xml_function(xml_root)
        if not one_chunk:
            skip = done
            while db and done and done > 0 and (total_rec == '?' or skip < total_rec):
                chunk_num += 1
                print(f'\t\tChunk #{chunk_num} {skip}/{total_rec}...')
                req = (_api_request_prefix +
                       f'<ParentApiDocumentId>{apiDocumentId}</ParentApiDocumentId>'
                       f'<Top>{chunk_size}</Top>'
                       f'<Skip>{skip}</Skip>' +
                       _api_request_suffix)
                # print('\t\tSend API request:',req)
                xml_root = _get_xml_root(req, api_type)
                done = process_xml_function(xml_root)
                skip += done


def import_styles():
    # Request styles modified after start_date from Teamwork API
    # and save results to MySQL DB.
    # Each next run will use start_date according to previous run
    global db, start_date

    with db.cursor() as cursor:
        # We are starting from the modification time of the last received record
        cursor.execute('select max(RecModified) as startdate from StyleStream;')
        data = cursor.fetchone()
        if data['startdate']:
            start_date = data['startdate']
            if shift_ms:
                start_date += datetime.timedelta(milliseconds=shift_ms)
        start_date_ = start_date.isoformat(timespec='milliseconds')

    print(f'\tRequesting Styles modified from {start_date_}.')
    _multi_chunk_import('<Filters>'
                       f'<Filter Field="RecModified" Operator="Greater than or equal" Value="{start_date_}" />'
                       '</Filters>'
                       '<SortDescriptions>'
                       '<SortDescription Name="RecModified" Direction="Ascending" />'
                       '</SortDescriptions>',
                       'inventory-export',
                        _process_styles_xml)


_locs = '|'.join(TW_LOCATIONS)
_loc_count = len(TW_LOCATIONS)


def _process_rta_xml(xml_root):
    # Copy Styles to Items
    rtas = dict()
    done = 0
    for rta in xml_root.iter('LocationQuantity'):
        try:
            done += 1
            itemid = rta.find('ItemIdentifier').text
            qty = (float(rta.find('Qty').text) -
                   float(rta.find('CommittedQty').text) -
                   float(rta.find('DamagedQty').text))
            if itemid in rtas:
                rtas[itemid][0] += qty
                rtas[itemid][1] += 1
            else:
                rtas[itemid] = [qty, 1]  # second - location counter
        except Exception as e:
            print('\t\t\t', e)

    for itemid in rtas:
        with db.cursor() as cursor:
            cursor.execute('INSERT INTO Items (ItemId, Qty, LocCount, QtySent, QtyApiRequestTime) '
                           'VALUES (%s, %s, %s, NULL, %s) '
                           'ON DUPLICATE KEY UPDATE '
                           'QtySent = NULL, '
                           'Qty = case when QtyApiRequestTime = %s then Qty else 0 end + %s, '
                           'LocCount = case when QtyApiRequestTime = %s then LocCount else 0 end + %s, '
                           'QtyApiRequestTime = %s',
                           (itemid, rtas[itemid][0], rtas[itemid][1], apiRequestTime,
                            apiRequestTime, rtas[itemid][0],
                            apiRequestTime, rtas[itemid][1],
                            apiRequestTime,
                            ))

    print(f'\t\t\tRTA: {done} received, {len(rtas)} calculated, saved to DB "{twmysql._DB}"')
    if done > 0:
        _save_last_response('-rta')
    return done


def import_rta_by_item(item_id):
    # Request RTA by ItemId from Teamwork API
    # and save results to MySQL DB
    print(f'\tRequesting RTA for Item {item_id}.')

    _multi_chunk_import('<Settings>'
                       '<ItemIdentifierSetting>TeamworkId</ItemIdentifierSetting>'
                       '<LocationIdentifierSetting>TeamworkId</LocationIdentifierSetting>'
                       '</Settings>'
                       '<Filters>'
                       f'<Filter Field="ItemId" Operator="Equal" Value="{item_id}" />'
                       f'<Filter Field="LocationId" Operator="Contains" Value="{_locs}" />'
                       '</Filters>',
                       'location-quantity-export',
                        _process_rta_xml
                        #,True
                        )


def import_rta_by_date(date, run_by_item_at_the_end=False):
    # Request RTA modified after date from Teamwork API
    # and save results to MySQL DB
    print(f'\tRequesting RTA for all Items starting from {date}.')
    _multi_chunk_import('<Settings>'
                       '<ItemIdentifierSetting>TeamworkId</ItemIdentifierSetting>'
                       '<LocationIdentifierSetting>TeamworkId</LocationIdentifierSetting>'
                       '</Settings>'
                       '<Filters>'
                       # f'<Filter Field="ItemId" Operator="Equal" Value="9E925D6D-6398-4B29-828C-1A5BE8600F00" />'
                       f'<Filter Field="RecModified" Operator="Greater than or equal" Value="{date}" />'
                       f'<Filter Field="LocationId" Operator="Contains" Value="{_locs}" />'
                       '</Filters>',
                        'location-quantity-export',
                        _process_rta_xml)

    if run_by_item_at_the_end:
        global db
        with db.cursor() as cursor:
            cursor.execute('select ItemId from Items where LocCount < %s and Qty is not Null', (_loc_count,))
            while db:
                row = cursor.fetchone()
                if not row:
                    break
                import_rta_by_item(row['ItemId'])


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

        init_tw(args.drop)

        #import_rta_by_item('9E925D6D-6398-4B29-828C-1A5BE8600F00')

        import_styles()

        import_rta_by_date(dateutil.parser.parse('2000-01-01 00:00:00'))

    finally:
        if db:
            db.close()