import sys
from PyQt5 import QtWidgets  # sudo python3.6 -m pip install pyqt5 / win - install_ipython_notebook.bat ?

app = QtWidgets.QApplication(sys.argv)

win = QtWidgets.QWidget()

win.resize(650, 600)
win.setWindowTitle('Huray')

lblCentered = QtWidgets.QLabel('<center>Test</center>')
btnQuit = QtWidgets.QPushButton('&Exit')

vbox = QtWidgets.QVBoxLayout()
vbox.addWidget(lblCentered)
vbox.addWidget(btnQuit)

win.setLayout(vbox)
btnQuit.clicked.connect(app.quit)

win.show()

sys.exit(app.exec_())

