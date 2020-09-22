# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'zoo_SelectListWin.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_zoo_SelectListWin(object):
    def setupUi(self, zoo_SelectListWin):
        zoo_SelectListWin.setObjectName("zoo_SelectListWin")
        zoo_SelectListWin.resize(263, 524)
        self.verticalLayoutWidget = QtWidgets.QWidget(zoo_SelectListWin)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(20, 10, 221, 491))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.listWidget = QtWidgets.QListWidget(self.verticalLayoutWidget)
        self.listWidget.setObjectName("listWidget")
        self.verticalLayout.addWidget(self.listWidget)
        self.buttonBox = QtWidgets.QDialogButtonBox(self.verticalLayoutWidget)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(zoo_SelectListWin)
        self.buttonBox.accepted.connect(zoo_SelectListWin.accept)
        self.buttonBox.rejected.connect(zoo_SelectListWin.reject)
        QtCore.QMetaObject.connectSlotsByName(zoo_SelectListWin)

    def retranslateUi(self, zoo_SelectListWin):
        _translate = QtCore.QCoreApplication.translate
        zoo_SelectListWin.setWindowTitle(_translate("zoo_SelectListWin", "Select ICs/ICNs to remove:"))

