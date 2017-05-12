import os
import glob
import argparse
import xml.etree.ElementTree as ET

# pip install --upgrade ShopifyAPI / sudo python3.6 -m pip install --upgrade ShopifyAPI
# pip uninstall ShopifyAPI / sudo python3.6 -m pip uninstall --upgrade ShopifyAPI
# pip uninstall pyactiveresource / sudo python3.6 -m pip uninstall pyactiveresource
import shopify

import twmysql
import utils

# Shopify
API_KEY = 'ed295b157652f8fbe1ca8de4b8db4e72'
PASSWORD = 'bf7c0c7e9e085459c3eeb022d32e8202'
SHARED_SECRET = '5f6f9d277b736295637ca8e9fa642b41'
SHOP_NAME = 'vicrom'

# Global
recreate = False  # False - Delete existent product and create the new one, True - update old product

shop_url_short = f'{SHOP_NAME}.myshopify.com'
shop_url = f'https://{API_KEY}:{PASSWORD}@{shop_url_short}/admin'
session = None

err_count = 0  # total number of errors from first run (persistent)
db = None

def init():
    # Shopify init
    shopify.ShopifyResource.set_site(shop_url)
    shopify.Session.setup(api_key=API_KEY, secret=SHARED_SECRET)
    # session = shopify.Session(shop_url_short)
    # shopify.ShopifyResource.activate_session(session)
    # shop = shopify.Shop.current()

    utils.mkdirs()

    # MySql init
    global db
    db = twmysql.get_db()

def run():
    # Send data from MySQL to Shopify
    done = 0
    global tot_count, err_count

    print(f'\tLooking for not sent Styles in DB {twmysql._DB}')
    # Copy Styles to Items!
    with db.cursor() as cursor:
        cursor.execute('SELECT s.ID as ID, s.StyleNo, s.StyleXml, s.SyncRunsID, '
                       'coalesce(s.ProductID,(SELECT ProductID FROM Styles WHERE ID<S.ID AND s.StyleNo=StyleNo ORDER BY RecModified Desc LIMIT 1)) ProductID '
                       'FROM Styles s '
                       #DEBUG 'WHERE s.ProductSent IS NULL '
                       'WHERE s.ID BETWEEN 119 AND 123 ' #DEBUG
                       'ORDER BY s.RecModified')
        print('\t\t', '\t'.join(('#', 'ID', 'VN', 'Er', 'Style', 'Prod', 'Modif', 'Title', 'ErrMes')))
        while True:
            row = cursor.fetchone()
            if not row:
                break
            style = ET.fromstring(row['StyleXml'])
            try:
                title = style.find('CustomText5').text \
                        or style.find('Description4').text  # DEBUG, remove it
                modif_time = style.find('RecModified').text
                styleno = style.find('StyleNo').text
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
                varcount = 0
                for item in items:
                    varcount += 1
                    variant = dict()
                    variant['sku'] = item.find('PLU').text or 'Empty PLU'
                    # ??? 'barcode'
                    # for upc in item.iter('UPC'):
                    #     variant['barcode'] = upc.attrib['Value']
                    #     break

                    # "option1" goes instead of "title": if "option1" not filled Shopify creates Empty Variant
                    variant['option1'] = ' '.join(filter(None, (
                                       style.find('CustomText5').text,
                                       item.find('Attribute1').text,
                                       item.find('Attribute2').text,
                                       item.find('Attribute3').text,
                                       ))) or styleno + ' Empty CustomText5+Attribute1+Attribute2+Attribute3'

                    variant['price'] = float(item.find('BasePrice').text)
                    variants.append(variant)
                product.variants = variants

                product.save()

            except Exception as e:
                #print('\t\t\t', e, shopify.Session.responce.code)
                err_count += 1
                errmes = e
                err_delta = 1

            else:
                if product.errors:
                    err_count += 1
                    errmes = product.errors.full_messages()
                    err_delta = 1
                    # print('\t\t\t', errmes)
                else:
                    errmes = None
                    err_delta = 0
            finally:
                done += 1
                print('\t\t', '\t'.join((str(done), str(row['ID']), str(varcount), str(err_count), styleno,
                                         str(oldProductID or '-New-'),
                                         modif_time,
                                         title,
                                         str(errmes or ''))))
                with db.cursor() as upd:
                    if product and product.id:
                        upd.execute('UPDATE Styles SET '
                                    'ProductSent = CURRENT_TIMESTAMP(3), '
                                    'ProductID = %s, '
                                    'OldProductID = %s, '
                                    'VariantsCount = %s, '
                                    'ErrMes = %s '
                                    'WHERE ID = %s',
                                    (product.id,
                                     oldProductID,
                                     varcount,
                                     errmes,
                                     row['ID']
                                     )
                                    )
                    upd.execute('UPDATE SyncRuns SET '
                                'DstLastSendTime = CURRENT_TIMESTAMP(3), '
                                'DstProcessedEntities = DstProcessedEntities + 1, '
                                'DstErrorCount = DstErrorCount + %s '
                                'WHERE ID = %s',
                                (#recmod,
                                 err_delta,
                                 row['SyncRunsID']
                                 )
                                )
    print(f'\tStyles sent to "{shop_url_short}": {done-err_count}. Errors: {err_count} ')
    return done


def cleanup():
    print('\tCleanup started! Do not Interrupt please!...')

    # Cleanup XML Received
    for f in glob.glob(os.path.join('xml', '*.xml')):
        os.remove(f)

    # Mark All Styles as UnSent
    with db.cursor() as cursor:
        cursor.execute('UPDATE Styles SET '
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

    init()

    # Command line arguments processing
    parser = argparse.ArgumentParser(description='Sending Styles from MySql to Shopify ' + shop_url)
    parser.add_argument('--cleanup', nargs='?', type=bool, const=False, help=f'Cleanup XML Received and Delete ALL Products (False)')
    args = parser.parse_args()
    if args.cleanup:
        cleanup()

    run()

    shopify.ShopifyResource.clear_session()
