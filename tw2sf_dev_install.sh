#!/bin/bash         

sudo apt install git --yes

cd
git clone https://github.com/chshkhr/tw2sf.git
cd tw2sf
chmod 700 install.sh
./install.sh
