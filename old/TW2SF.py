import re, os, glob, time, argparse, pickle
import requests
import xml.etree.ElementTree as ET
import datetime
import dateutil.parser
from pathlib import Path

import shopify  # pip install --upgrade ShopifyAPI

# Shopify
API_KEY = '31a29b1f8ec4c1440ee60d0134a66dd0'
PASSWORD = '529fe579821097684f543a8660c714f7'
SHARED_SECRET = '50a5e6d13d4dd436f2a78fe3cb276b66'
SHOP_NAME = 'cloudworktest'

# Teamwork
TW_API_KEY = '9CA9E29D-D258-48DC-886E-A507F55A03D6'
TW_URL = 'https://hattestchq.teamworkinsight.com/'

# Global
start_date = '2017-01-24T00:00:00'  # (persistent)
shift_ms = -5000
start_date_ = ''  # start_date_ = start_date + shift_ms
chunk_size = 100  # Number of records per one request
chunk_num = 0  # Current chunk number
recreate = False  # False - Delete existent product and create the new one, True - update old product

apiDocumentId = ''
shop_url = f'https://{API_KEY}:{PASSWORD}@{SHOP_NAME}.shopify.com/admin'
style2product = dict()  # mapping between product ID in Teamwork and Shopify (persistent)
pickle_fn = 'tw2sf.pickle'  # file with persistent variables
tot_count = 0  # total number of products transferred from firs run (persistent)
err_count = 0  # total number of errors from firs run (persistent)


def save_xml(r):
    # Saving XML Response content to file
    fn = os.path.join('xml', datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]+'.xml')
    print('Saving Response to', fn, '...')
    with open(fn, 'bw') as f:
        f.write(r.content)


def get_root(r):
    # Get Root from XML Response, removing All XML NameSpaces
    return ET.fromstring(re.sub(r'\sxmlns="[^\"]+"', '', r.content.decode('utf-8'), flags=re.MULTILINE))


def chunk_transfer(req):
    # Get XML from Teamwork and Send it to Shopify
    done = 0
    global chunk_num, apiDocumentId, start_date, tot_count, err_count, start_date_
    chunk_num += 1
    print(f'Requesting Styles modified from {start_date_}. Chunk #{chunk_num}...')
    data = {'Data': req,
            'Source': 'VC_Test', 'UseApiVersion2': 'true',
            'ApiKey': TW_API_KEY, 'Async': 'true',
            'ApiRequestType': 'inventory-export'}
    r = requests.post(TW_URL + 'api.ashx', data=data)

    # Get XML from Teamwork
    root = get_root(r)
    a = root.attrib['ApiDocumentId']
    if apiDocumentId == '':
        apiDocumentId = a
    status = root.attrib['Status']
    while status == 'InProcess':
        time.sleep(5)
        r = requests.post(TW_URL + 'ApiStatus.ashx', data={'ID': a})
        root = get_root(r)
        status = root.attrib['Status']
    save_xml(r)

    # Copy Styles to Items
    for style in root.iter('Style'):
        try:
            title = style.find('Description4').text
            start_date = style.find('RecModified').text  # next time we'll start from this date
            styleno = style.find('StyleNo').text
            print('\t', tot_count, done, err_count, start_date, styleno, title)
            if styleno in style2product:
                product_id = style2product[styleno]
                if product_id:
                    try:
                        product = shopify.Product.find(product_id)
                    except Exception:
                        product = shopify.Product()
                    else:
                        if recreate:
                            print('\t\tDeleting...')
                            product.destroy()
                            product = shopify.Product()
                del style2product[styleno]
            else:
                product = shopify.Product()
            product.title = title
            product.product_type = style.find('Class').text
            product.vendor = style.find('PrimaryVendor').text
            product.option1 = style.find('AttributeSet1').text
            product.option2 = style.find('AttributeSet2').text

            # Copy Items to Variants
            items = style.iter('Item')
            variants = []
            varcount = 0
            for item in items:
                varcount += 1
                if varcount>100:
                    print('\t\tMax number of Variants reached!')
                    break
                variant = dict()
                variant['sku'] = item.find('PLU').text
                variant['option1'] = item.find('Attribute1').text
                t = item.find('Attribute2').text
                if t:
                    variant['option1'] += ' ' + t
                variant['price'] = float(item.find('BasePrice').text)
                for upc in item.iter('UPC'):
                    variant['barcode'] = upc.attrib['Value']
                    break
                variants.append(variant)
            product.variants = variants

            product.save()

        except Exception as e:
            print('\t\t', e)
            err_count += 1
        else:
            if product.errors:
                err_count += 1
                print('\t\t', product.errors.full_messages())
            else:
                # Save current state to file
                style2product[styleno] = product.id
                with open(pickle_fn, 'bw') as file:
                    pickle.dump(
                        {'style2product': style2product,
                         'startdate': start_date,
                         'totcount': tot_count,
                         'errcount': err_count},
                        file)

        finally:
            done += 1
            tot_count += 1

    print(f'\t{done} styles found in the Response')
    return done


def init():
    # Shopify Preparation
    shopify.ShopifyResource.set_site(shop_url)
    shopify.Session.setup(api_key=API_KEY, secret=SHARED_SECRET)
    # shop = shopify.Shop.current()

    global style2product, start_date, tot_count, err_count

    if Path(pickle_fn).is_file():
        # Restore Saved Data
        with open(pickle_fn, 'br') as file:
            pd = pickle.load(file)
        style2product = pd['style2product']
        start_date = pd['startdate']
        tot_count = pd['totcount']
        err_count = pd['errcount']
    else:
        # Cleanup XML Received
        for f in glob.glob(os.path.join('xml','*.xml')):
            os.remove(f)
        # Delete ALL Products if Correspondence Matrix to found
        if input(f'Delete ALL Products on {SHOP_NAME}.shopify.com to avoid Duplicated Products?!\n' +
                 '(type YES for confirmation)') == 'YES':
            products = True
            i = 0
            while products:
                products = shopify.Product.find()
                for product in products:
                    i += 1
                    print(i, product.title, 'Deleting...')
                    product.destroy()

    global start_date_
    dt = dateutil.parser.parse(start_date)
    dt += datetime.timedelta(milliseconds=shift_ms)
    start_date_ = dt.isoformat(timespec='milliseconds')


def run():
    global start_date_, apiDocumentId, chunk_size
    # Main Loop
    done = chunk_transfer(f'''<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                        xmlns="http://microsoft.com/wsdl/types/">
                        <Request>
                        <Filters>
                        <Filter Field="RecModified" Operator="Greater than or equal"
                        Value="{start_date_}" />
                        </Filters>
                        <SortDescriptions>
                        <SortDescription Name="RecModified" Direction="Ascending" />
                        </SortDescriptions>
                        <Top>{chunk_size}</Top>
                        </Request>
                        </ApiDocument>
                        ''')
    skip = done
    while done > 0:
        done = chunk_transfer(f'''<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                            xmlns="http://microsoft.com/wsdl/types/">
                            <Request>
                            <ParentApiDocumentId>{apiDocumentId}</ParentApiDocumentId>
                            <Top>{chunk_size}</Top>
                            <Skip>{skip}</Skip>
                            </Request>
                            </ApiDocument>
                            ''')
        skip += done

if __name__ == '__main__':

    init()

    # Command line arguments processing
    parser = argparse.ArgumentParser(description='Getting Teamwork Inventory from ' + TW_URL)
    parser.add_argument('-c', '--chunk', type=int, help=f'Chunk Size ({chunk_size})')
    parser.add_argument('-s', '--start', help=f'Start Date ({start_date})')
    args = parser.parse_args()
    if args.chunk:
        chunk_size = int(args.chunk)
    if args.start:
        start_date = args.start

    run()
