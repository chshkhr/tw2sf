#!/bin/bash         

sudo apt install git --yes

cd
git clone https://chursin_v@bitbucket.org/chursin_v/tw2sf.git
cd tw2sf
chmod 700 install.sh
./install.sh
