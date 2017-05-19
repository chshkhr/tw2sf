import argparse
import xml.etree.ElementTree as ET

# pip install --upgrade ShopifyAPI / sudo python3.6 -m pip install --upgrade ShopifyAPI
# pip uninstall ShopifyAPI --yes / sudo python3.6 -m pip uninstall ShopifyAPI --yes
# pip uninstall pyactiveresource --yes / sudo python3.6 -m pip uninstall pyactiveresource --yes
import shopify

import twmysql
import utils
import time

# Shopify
API_KEY = 'ed295b157652f8fbe1ca8de4b8db4e72'
PASSWORD = 'bf7c0c7e9e085459c3eeb022d32e8202'
SHARED_SECRET = '5f6f9d277b736295637ca8e9fa642b41'
SHOP_NAME = 'vicrom'
# https://help.shopify.com/api/getting-started/response-status-codes
MAX_REPEAT = 5  # max number of retry on response errors 429, 503?, 504?
# Only these channels will be transfered to Shopify
CHANNELS = ['store','Amazon','Magento']
PUBLISH_ZERO_QTY = False

# Global
recreate = False  # True - Delete existent product and create the new one, False - update old products

shop_url_short = f'{SHOP_NAME}.myshopify.com'
shop_url = f'https://{API_KEY}:{PASSWORD}@{shop_url_short}/admin'

err_count = 0  # total number of errors from first run (persistent)
db = None

def init_sf():
    # Shopify init
    shopify.ShopifyResource.set_site(shop_url)
    shopify.Session.setup(api_key=API_KEY, secret=SHARED_SECRET)

    utils.mkdirs()

    # MySql init
    global db
    db = twmysql.get_db()

def export_styles():
    # Send data from MySQL to Shopify
    done = 0
    filtered = 0
    global tot_count, err_count, db

    # We'll send only the last version of each style (ErrCode=-2 means this Style Version is Obsolete)
    with db.cursor() as cursor:
        cursor.execute('UPDATE teamwork.StyleStream s1 ' 
                       'JOIN teamwork.StyleStream s2 ON s1.StyleNo=s2.StyleNo '
                       'SET s1.ProductSent = CURRENT_TIMESTAMP(3), '
                       's1.ErrCode = -2 '
                       'WHERE s1.ProductSent IS NULL '
                       'AND s2.ProductSent IS NULL '
                       'AND s1.RecModified < s2.RecModified')

    print(f'\tLooking for not sent Styles in DB "{twmysql._HOST}:{twmysql._DB}"')
    # Copy Styles to Items!
    with db.cursor() as cursor:
        cursor.execute('SELECT s.ID as ID, s.StyleNo, s.StyleXml, s.SyncRunsID, '
                       'coalesce(s.ProductID,'
                       '(SELECT ProductID FROM Styles WHERE StyleID=s.StyleID),'
                       '(SELECT ProductID FROM StyleStream WHERE ID<S.ID AND s.StyleNo=StyleNo ORDER BY RecModified Desc LIMIT 1)) ProductID '
                       #DEBUG 'FROM StyleStream s '
                       'WHERE s.ProductSent IS NULL '
                       'WHERE s.ID BETWEEN 170 AND 190 '
                       'ORDER BY s.RecModified, s.ID')
        print('\t\t', '\t'.join(('#', 'ID', 'Var', 'Ers', 'ErC', 'StNo', 'PrID', 'Modif', 'Qty', 'Title', 'ErrMes')))
        repeat = 0
        while db:
            if repeat > 0:
                repeat += 1
                if repeat <= MAX_REPEAT:
                    time.sleep(repeat*repeat)
                else:
                    repeat = 0
            if repeat == 0:
                row = cursor.fetchone()
            if not row:
                break
            style = ET.fromstring(row['StyleXml'])

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
            if not channel_active:
                filtered += 1

            try:
                title = style.find('CustomText5').text or style.find('Description4').text

                modif_time = style.find('RecModified').text
                styleno = style.find('StyleNo').text
                styleid = style.find('StyleId').text
                oldProductID = row['ProductID']
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
                    if not channel_active:
                        continue
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
                    variant = dict()
                    variant['sku'] = item.find('PLU').text or 'Empty PLU'
                    # ??? 'barcode'

                    # "option1" goes instead of "title": if "option1" not filled Shopify creates Empty Variant
                    variant['option1'] = ' '.join(filter(None, (
                                       style.find('CustomText5').text,
                                       item.find('Attribute1').text,
                                       item.find('Attribute2').text,
                                       item.find('Attribute3').text,
                                       ))) or styleno + ' Empty CustomText5+Attribute1+Attribute2+Attribute3'
                    itemid = item.find('ItemId').text
                    variant['ItemId'] = itemid

                    variant['price'] = float(item.find('BasePrice').text)

                    variant['inventory_management'] = 'shopify'
                    variant['inventory_policy'] = 'continue'
                    variant['inventory_quantity'] = 0
                    with db.cursor() as qry:
                        qry.execute('SELECT Qty FROM Items WHERE ItemId = %s',(itemid,))
                        val = qry.fetchone()
                        if val:
                            var_qty = val['Qty']
                            if var_qty and var_qty>0:
                                var_qty = int(var_qty)
                                variant['inventory_quantity'] = var_qty
                                style_qty += var_qty
                    variants.append(variant)

                if PUBLISH_ZERO_QTY or style_qty>0 or oldProductID:  # new with qty>0 or old
                    product.variants = variants
                    if not channel_active or style_qty==0:
                        product.published_at = None
                    product.save()

            except (KeyboardInterrupt, SystemExit) as e:
                db = None
            except Exception as e:
                err_count += 1
                err_mes = e
                err_code = -1  # means "it's Exception"
                repeat = 0  # do not retry on any Exception
                err_delta = 1

            else:
                if product.errors:
                    err_mes = product.errors.full_messages()
                    err_code = product.errors.code
                    if err_code in [429, 503, 504]:
                        if repeat==0:
                            repeat = 1
                        elif repeat >= MAX_REPEAT:
                            err_count += 1
                    else:
                        err_count += 1
                    err_delta = 1
                else:
                    err_mes = None
                    err_code = 0
                    err_delta = 0
                    repeat = 0
            finally:
                if not db:
                    print('\tUSER TERMINATION!')
                else:
                    if repeat <= 1:
                        done += 1
                    if not channel_active:
                        err_code = -3  # ErrCode=-3 means this Style belongs to inactive Channel
                    if not PUBLISH_ZERO_QTY and style_qty == 0:
                        err_code = -4  # ErrCode=-4 means total style qty equals zero
                        filtered += 1
                    if product:
                        productID = product.id
                    print('\t\t', '\t'.join((str(done), str(row['ID']), str(varcount), str(err_count), str(err_code),
                                             styleno, str(oldProductID or 'New-'+str(productID)),
                                             modif_time, str(style_qty),
                                             title,
                                             str(err_mes or ''))))
                    with db.cursor() as upd:
                        upd.execute('UPDATE StyleStream SET '
                                    'ProductSent = case when %s=0 then CURRENT_TIMESTAMP(3) else Null end, '
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

            if db and productID and not err_delta:
                # Save mappings Items to Variants:
                with db.cursor() as ins:
                    for index, variant in enumerate(product.variants):
                        ins.execute('INSERT INTO Items (ItemId, StyleId, VariantID, QtySent) '
                                    'VALUES (%s, %s, %s, CURRENT_TIMESTAMP(3)) '
                                    'ON DUPLICATE KEY UPDATE StyleId = %s, VariantID = %s',
                                    (variants[index]['ItemId'],  # variant['ItemId'] lost after product.save()
                                     styleid,
                                     variant.id,
                                     styleid,
                                     variant.id,
                                     )
                                )

    print(f'\tProcessed: {done}. Filtered/Deactivated: {filtered}. Errors: {err_count}. Sent to "{shop_url_short}": {done-err_count-filtered}.')
    return done


def cleanup():
    print('\tCleanup started! Do not Interrupt please!...')

    # Mark All Styles as UnSent
    with db.cursor() as cursor:
        cursor.execute('UPDATE StyleStream SET '
                       'ProductID = NULL,'
                       'ProductSent = NULL, '
                       'OldProductID = NULL,'
                       'VariantsCount = NULL, '
                       'ErrMes = NULL;')
        cursor.execute('UPDATE SyncRuns SET '
                       'DstProcessedEntities = 0, '
                       'DstErrorCount = 0;')

    # Delete ALL Products on Shopify
    products = True
    i = 0
    while products:
        products = shopify.Product.find()
        for product in products:
            i += 1
            print('\t\t', i, product.title, 'Deleting...')
            product.destroy()

    print('\tCleanup finished.')


if __name__ == '__main__':

    init_sf()

    # Command line arguments processing
    parser = argparse.ArgumentParser(description='Sending Styles from MySql to Shopify ' + shop_url)
    parser.add_argument('--cleanup', nargs='?', type=bool, const=False, help=f'Cleanup XML Received and Delete ALL Products (False)')
    args = parser.parse_args()
    if args.cleanup:
        cleanup()

    export_styles()