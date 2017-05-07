python .\tw2sf_service.py install
rem sc config TeamworkSvc start=demand
sc config TeamworkSvc start=auto
net start TeamworkSvc