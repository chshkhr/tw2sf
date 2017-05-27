import argparse
import xml.etree.ElementTree as ET
from sys import platform

# pip install --upgrade ShopifyAPI / sudo python3.6 -m pip install --upgrade ShopifyAPI
# pip uninstall ShopifyAPI --yes / sudo python3.6 -m pip uninstall ShopifyAPI --yes
# pip uninstall pyactiveresource --yes / sudo python3.6 -m pip uninstall pyactiveresource --yes
import shopify

import twmysql
import utils
import time

# Shopify constants
if platform == 'linux' or platform == 'linux2':
    API_KEY = 'ed295b157652f8fbe1ca8de4b8db4e72'
    PASSWORD = 'bf7c0c7e9e085459c3eeb022d32e8202'
    SHARED_SECRET = '5f6f9d277b736295637ca8e9fa642b41'
    SHOP_NAME = 'vicrom'
else:
    API_KEY = '31a29b1f8ec4c1440ee60d0134a66dd0'
    PASSWORD = '529fe579821097684f543a8660c714f7'
    SHARED_SECRET = '50a5e6d13d4dd436f2a78fe3cb276b66'
    SHOP_NAME = 'cloudworktest'

# Settings
MAX_REPEAT = 5  # max number of retry on response errors 429, 503?, 504?
                # https://help.shopify.com/api/getting-started/response-status-codes
MAX_VARIANTS = 100  # used to avoid error 'Max variants exceeded', variants after MAX_VARIANTS will be ignored
CHANNELS = ['store','Amazon','Magento']  # Only these channels will be sent to Shopify
recreate = False  # True - Delete existent product and create the new one, False - update old products

# Global variables
shop_url_short = f'{SHOP_NAME}.myshopify.com'
shop_url = f'https://{API_KEY}:{PASSWORD}@{shop_url_short}/admin'
err_count = 0  # total number of errors from first run (persistent)
done = 0
filtered = 0
tot_count = 0
db = None


def init_sf():
    # Shopify init
    shopify.ShopifyResource.set_site(shop_url)
    shopify.Session.setup(api_key=API_KEY, secret=SHARED_SECRET)

    utils.mkdirs()

    # MySql init
    global db
    db = twmysql.get_db()
    return db is not None


def _export_style(row, publish_zero_qty=False):
    style = ET.fromstring(row['StyleXml'])
    oldProductID = row['ProductID']

    global done, filtered
    global tot_count, err_count, db
    repeat = 0
    err_mes = None
    product = None
    productID = None
    err_delta = 0
    varcount = 0

    # <EChannels>
    #  <EChannel Name = "Amazon" Status = "EcOffer" ECommerceId = "15287" />
    #  <EChannel Name = "Magento" Status = "EcSuspended" ECommerceId = "15287" />
    # </EChannels>
    # for channel in style.iter('EChannel'):
    #     channel_active = channel.attrib['Name'] in CHANNELS \
    #                      and channel.attrib['Status'] == 'EcOffer'
    #     if channel_active:
    #         break

    # DEBUG Filter by !Variant! Channel
    channel_active = False
    for channel in style.iter('Channel'):
        channel_active = channel.attrib['Name'] in CHANNELS
        if channel_active:
            break

    while -1 < repeat < MAX_REPEAT:
        if repeat > 0:
            time.sleep(repeat * repeat)

        try:
            styleno = style.find('StyleNo').text
            title = (style.find('CustomText5').text or
                     style.find('Description4').text or
                     styleno)

            modif_time = style.find('RecModified').text
            styleid = style.find('StyleId').text
            if oldProductID:
                try:
                    product = shopify.Product.find(oldProductID)
                except Exception as e:  # PyCharm BUG: do not remove "as e"
                    product = shopify.Product()
                else:
                    if recreate:
                        oldProductID = None
                        print('\t\tDeleting...')
                        product.destroy()
                        product = shopify.Product()
            else:
                product = shopify.Product()

            product.title = title

            product.body_html = style.find('CustomText1').text or \
                                title + ' <font color="RED">Empty CustomText1!</font>'

            # ??? Style SKU	- Style No

            product.option1 = style.find('AttributeSet1').text or 'Empty AttributeSet1'
            product.option2 = style.find('AttributeSet2').text or 'Empty AttributeSet2'
            product.option3 = style.find('AttributeSet3').text or 'Empty AttributeSet3'

            product.vendor = style.find('PrimaryVendor').text or 'Empty PrimaryVendor'

            # League - (CustomLookup3) Team - (CustomLookup1)
            product.tags = ', '.join(filter(None, (
                style.find('CustomLookup3').text,
                style.find('CustomLookup1').text,
            )))

            # Copy Items to Variants
            items = style.iter('Item')
            variants = []
            style_qty = 0;
            for item in items:
                varcount += 1
                if varcount > MAX_VARIANTS:
                    break
                sku = item.find('PLU').text or f'Empty PLU {varcount}'
                variant = dict()
                if oldProductID and product.variants:
                    for v in product.variants:
                        if v.sku == sku:
                            variant['id'] = v.id
                            break
                variant['sku'] = sku
                # ??? 'barcode'

                # "option1" goes instead of "title": if "option1" not filled Shopify creates Empty Variant
                variant['option1'] = ' '.join(filter(None, (
                    style.find('CustomText5').text,
                    item.find('Attribute1').text,
                    item.find('Attribute2').text,
                    sku,
                    # item.find('Attribute3').text,
                )))  # or styleno + ' Empty CustomText5+Attribute1+Attribute2+Attribute3'
                itemid = item.find('ItemId').text
                variant['ItemId'] = itemid

                variant['price'] = float(item.find('BasePrice').text)

                variant['inventory_management'] = 'shopify'
                variant['inventory_policy'] = 'continue'
                variant['inventory_quantity'] = 0
                with db.cursor() as qry:
                    qry.execute('SELECT Qty FROM Items WHERE ItemId = %s', (itemid,))
                    val = qry.fetchone()
                    if val:
                        var_qty = val['Qty']
                        if var_qty and var_qty >= 0:
                            var_qty = int(var_qty)
                            variant['inventory_quantity'] = var_qty
                            style_qty += var_qty
                variants.append(variant)

            if publish_zero_qty or style_qty > 0 or oldProductID:  # new with qty>0 or old
                product.variants = variants
                if not channel_active or style_qty == 0:
                    product.published_at = None
                product.save()

        except Exception as e:
            err_count += 1
            err_mes = e
            err_code = -1  # means "it's Exception"
            repeat = MAX_REPEAT  # do not retry on any Exception
            err_delta = 1

        else:
            if product.errors:
                err_mes = product.errors.full_messages()
                err_code = product.errors.code
                if err_code in [429, 503, 504]:
                    if repeat == 0:
                        repeat = 1
                    elif repeat >= MAX_REPEAT:
                        err_count += 1
                else:
                    err_count += 1
                err_delta = 1
            elif varcount > MAX_VARIANTS:
                err_mes = f'Max number of variants exceeded! Only first {MAX_VARIANTS} variants sent!'
                err_code = -5
                repeat = -1
            else:
                err_mes = None
                err_code = 0
                err_delta = 0
                repeat = -1
        finally:
            if repeat <= 1:
                done += 1
            if not channel_active:
                err_code = -3  # ErrCode=-3 means this Style belongs to inactive Channel
            if not publish_zero_qty and style_qty == 0:
                err_code = -4  # ErrCode=-4 means total style qty equals zero
                filtered += 1
            if product:
                productID = product.id
            print('\t\t', '\t'.join((str(done), str(row['ID']), str(varcount), str(err_count), str(err_code),
                                     styleno, str(oldProductID or 'New-' + str(productID)),
                                     modif_time, str(style_qty),
                                     title,
                                     str(err_mes or ''))))
            with db.cursor() as upd:
                upd.execute('UPDATE StyleStream SET '
                            'ProductSent = case when %s<=0 then CURRENT_TIMESTAMP(3) else Null end, '
                            'ProductID = %s, '
                            'OldProductID = %s, '
                            'VariantsCount = %s, '
                            'ErrMes = %s, '
                            'ErrCode = %s, '
                            'RetryCount = RetryCount + 1 '
                            'WHERE ID = %s',
                            (repeat,
                             productID,
                             oldProductID,
                             varcount,
                             err_mes,
                             err_code,
                             row['ID']
                             )
                            )
            with db.cursor() as upd:
                upd.execute('UPDATE SyncRuns SET '
                            'DstLastSendTime = CURRENT_TIMESTAMP(3), '
                            'DstProcessedEntities = DstProcessedEntities + 1, '
                            'DstErrorCount = DstErrorCount + %s '
                            'WHERE ID = %s',
                            (err_delta,
                             row['SyncRunsID']
                             )
                            )
            if productID and not err_delta:
                # Save mappings Items to Variants:
                with db.cursor() as cur:
                    for index, variant in enumerate(product.variants):
                        cur.execute('INSERT INTO Items (ItemId, StyleId, VariantID, QtySent) '
                                    'VALUES (%s, %s, %s, CURRENT_TIMESTAMP(3)) '
                                    'ON DUPLICATE KEY UPDATE '
                                    'StyleId = %s, '
                                    'VariantID = %s, '
                                    'QtySent = case when %s > 0 then CURRENT_TIMESTAMP(3) else Null end',
                                    (variants[index]['ItemId'],  # variant['ItemId'] lost after product.save()
                                     styleid,
                                     variant.id,
                                     styleid,
                                     variant.id,
                                     product.id,
                                     )
                                    )
                    if err_code == -5:
                        cur.execute('UPDATE Items SET QtySent = CURRENT_TIMESTAMP(3) '
                                    'WHERE StyleId = %s '
                                    'AND QtySent IS NULL ',
                                    (styleid,))

            return product


_style_qry = ('SELECT s.ID as ID, s.StyleNo, s.StyleXml, s.SyncRunsID, '
             'coalesce(s.ProductID,'
             '(SELECT ProductID FROM Styles WHERE StyleID=s.StyleID), '
             '(SELECT ProductID FROM StyleStream WHERE ID<s.ID AND s.StyleNo=StyleNo ORDER BY RecModified Desc LIMIT 1)) ProductID '
             'FROM StyleStream s '
             )


def _print_header():
    print('\t\t', '\t'.join(('#', 'ID', 'Var', 'Ers', 'ErC', 'StNo', 'PrID', 'Modif', 'Qty', 'Title', 'ErrMes')))


def _print_footer():
    global done, filtered
    global tot_count, err_count
    print(f'\t\tProcessed: {done}. Filtered/Deactivated: {filtered}. Errors: {err_count}. Sent to "{shop_url_short}": {done-err_count-filtered}.')


def export_styles(publish_zero_qty=False):
    # Send not sent Styles from MySQL to Shopify and mark them as sent
    global done, filtered
    global tot_count, err_count, db
    done = 0
    filtered = 0

    # We'll send only the last version of each style (ErrCode=-2 means this Style Version is Obsolete)
    with db.cursor() as cursor:
        cursor.execute('UPDATE StyleStream s ' 
                       'JOIN StyleStream s2 ON s.StyleNo=s2.StyleNo '
                       'SET s.ProductSent = CURRENT_TIMESTAMP(3), '
                       's.ErrCode = -2 '
                       'WHERE s.ProductSent IS NULL '
                       'AND s2.ProductSent IS NULL '
                       'AND s.RecModified < s2.RecModified ')

    print(f'\tLooking for not sent Styles in DB "{twmysql.HOST} {twmysql.DB}"...')
    # Copy Styles to Items!
    with db.cursor() as cursor:
        cursor.execute(_style_qry +
                       'WHERE s.ProductSent IS NULL '
                       # DEBUG 'WHERE s.ID BETWEEN 170 AND 190 '
                       'ORDER BY s.RecModified, s.ID')
        first_run = True
        while True:
            row = cursor.fetchone()
            if not row:
                break
            if first_run:
                first_run = False
                _print_header()
            _export_style(row, publish_zero_qty)
    if row:
        _print_footer()


def export_qty(resend=False):
    # Send RTA data to Shopify and mark them as sent
    global done, filtered
    global tot_count, err_count, db
    done = 0
    filtered = 0

    print(f'\tLooking for not sent RTA in DB "{twmysql.HOST} {twmysql.DB}"...')
    if resend:
        s = ''
    else:
        s = 'AND QtySent IS NULL '
    with db.cursor() as cursor:
        cursor.execute('SELECT DISTINCT StyleId '
                       'FROM Items '
                       'WHERE Qty >= 0 '
                       'AND StyleId IS NOT NULL ' +
                       s
                       )
        first_run = True
        while True:
            row = cursor.fetchone()
            if not row:
                break
            if first_run:
                first_run = False
                _print_header()
            with db.cursor() as cursor2:
                cursor2.execute(_style_qry + 'WHERE s.StyleID=%s', (row['StyleId'],))
                row2 = cursor2.fetchone()
                if row2:
                    _export_style(row2, publish_zero_qty=True)
    if row:
        _print_footer()


def cleanup():
    # Run it to start from scratch
    print('\tCleanup started...')

    # Mark All Styles as UnSent
    with db.cursor() as cursor:
        cursor.execute('UPDATE StyleStream SET '
                       'ProductID = NULL,'
                       'ProductSent = NULL, '
                       'OldProductID = NULL,'
                       'VariantsCount = NULL, '
                       'ErrMes = NULL '
                       )
        cursor.execute('UPDATE SyncRuns SET '
                       'DstProcessedEntities = 0, '
                       'DstErrorCount = 0 '
                       )
        cursor.execute('UPDATE Items SET '
                       'VariantID = Null, '
                       'QtySent = Null '
                       )
        cursor.execute('UPDATE Styles SET '
                       'ProductID = Null '
                       )

    # Delete ALL Products on Shopify
    products = True
    i = 0
    while products:
        products = shopify.Product.find()
        for product in products:
            i += 1
            print('\t\t', i, product.title, 'Deleting...')
            product.destroy()

    print('\tCleanup finished!')


if __name__ == '__main__':

    if init_sf():
        # Command line arguments processing
        parser = argparse.ArgumentParser(description='Sending Styles from MySql to Shopify ' + shop_url)
        parser.add_argument('--cleanup', nargs='?', type=bool, const=False,
                            help=f'Cleanup XML Received and Delete ALL Products (False)')
        args = parser.parse_args()
        if args.cleanup:
            cleanup()

        export_styles()

        export_qty()

