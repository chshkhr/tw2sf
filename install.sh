wget https://www.python.org/ftp/python/3.6.1/Python-3.6.1.tgz
tar xvf Python-3.6.1.tgz
cd Python-3.6.1
./configure
sudo make altinstall
python3.6 -m pip install python-dateutil
python3.6 -m pip install requests
python3.6 -m pip install pymysql
python3.6 -m pip install --upgrade ShopifyAPI 


