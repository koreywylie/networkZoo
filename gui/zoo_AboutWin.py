# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'zoo_AboutWin.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_AboutWin(object):
    def setupUi(self, AboutWin):
        AboutWin.setObjectName("AboutWin")
        AboutWin.resize(600, 800)
        self.gridLayout = QtWidgets.QGridLayout(AboutWin)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(AboutWin)
        font = QtGui.QFont()
        font.setFamily("Liberation Serif")
        font.setPointSize(18)
        font.setBold(False)
        font.setWeight(50)
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.textBrowser = QtWidgets.QTextBrowser(AboutWin)
        self.textBrowser.setObjectName("textBrowser")
        self.verticalLayout.addWidget(self.textBrowser)
        self.buttonBox = QtWidgets.QDialogButtonBox(AboutWin)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Close|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)
        self.gridLayout.addLayout(self.verticalLayout, 1, 1, 1, 1)

        self.retranslateUi(AboutWin)
        self.buttonBox.accepted.connect(AboutWin.accept)
        self.buttonBox.rejected.connect(AboutWin.reject)
        QtCore.QMetaObject.connectSlotsByName(AboutWin)

    def retranslateUi(self, AboutWin):
        _translate = QtCore.QCoreApplication.translate
        AboutWin.setWindowTitle(_translate("AboutWin", "Dialog"))
        self.label.setText(_translate("AboutWin", "Network Zoo v0.007"))

