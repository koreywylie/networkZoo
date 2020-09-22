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
        zoo_SelectListWin.resize(300, 600)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(zoo_SelectListWin)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.listWidget_selection = QtWidgets.QListWidget(zoo_SelectListWin)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.listWidget_selection.sizePolicy().hasHeightForWidth())
        self.listWidget_selection.setSizePolicy(sizePolicy)
        self.listWidget_selection.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.listWidget_selection.setObjectName("listWidget_selection")
        self.verticalLayout.addWidget(self.listWidget_selection)
        self.buttonBox = QtWidgets.QDialogButtonBox(zoo_SelectListWin)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(zoo_SelectListWin)
        self.buttonBox.accepted.connect(zoo_SelectListWin.accept)
        self.buttonBox.rejected.connect(zoo_SelectListWin.reject)
        QtCore.QMetaObject.connectSlotsByName(zoo_SelectListWin)

    def retranslateUi(self, zoo_SelectListWin):
        _translate = QtCore.QCoreApplication.translate
        zoo_SelectListWin.setWindowTitle(_translate("zoo_SelectListWin", "Select ICs/ICNs:"))

