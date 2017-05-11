#!/usr/bin/env bash
sudo apt-get update

wget http://www.openssl.org/source/openssl-1.0.2g.tar.gz
tar xvf openssl-1.0.2g.tar.gz
rm openssl-1.0.2g.tar.gz
cd openssl-1.0.2g
./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl
make
make test
sudo make install
cd

sudo apt-get install python3-dev libffi-dev libssl-dev python3-pip zlib1g-dev --yes
wget https://www.python.org/ftp/python/3.6.1/Python-3.6.1.tgz
tar xvf Python-3.6.1.tgz
rm Python-3.6.1.tgz
sudo gedit ~/Python-3.6.1/Modules/Setup.dist  # find SSL and uncomment lines
cd Python-3.6.1
./configure  # --enable-optimizations
sudo make altinstall
cd

#sudo apt-get install python3-dateutil
#sudo apt-get install python3-requests
#sudo apt-get install python3-pymysql
sudo python3.6 -m pip install python-dateutil
sudo python3.6 -m pip install requests
sudo python3.6 -m pip install pymysql
sudo python3.6 -m pip install --upgrade ShopifyAPI
sudo python3.6 -m pip install pyqt5

sudo apt install git --yes
git clone https://chursin_v@bitbucket.org/chursin_v/tw2sf.git
cd tw2sf
python3.6 tw2sf_runner.py

cd
wget https://download.jetbrains.com/python/pycharm-professional-2017.1.2.tar.gz
tar xvf pycharm-professional-2017.1.2.tar.gz
rm pycharm-professional-2017.1.2.tar.gz
cd pycharm-2017.1.2/bin

