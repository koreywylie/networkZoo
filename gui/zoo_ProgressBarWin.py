# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'zoo_ProgressBarWin.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(400, 200)
        self.progressWait = QtWidgets.QProgressBar(Dialog)
        self.progressWait.setGeometry(QtCore.QRect(70, 10, 261, 23))
        self.progressWait.setProperty("value", 0)
        self.progressWait.setObjectName("progressWait")
        self.verticalLayoutWidget = QtWidgets.QWidget(Dialog)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(9, 50, 381, 80))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.ic_fileName = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.ic_fileName.setAlignment(QtCore.Qt.AlignCenter)
        self.ic_fileName.setObjectName("ic_fileName")
        self.verticalLayout.addWidget(self.ic_fileName)
        self.CorrAmpersand = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.CorrAmpersand.setAlignment(QtCore.Qt.AlignCenter)
        self.CorrAmpersand.setObjectName("CorrAmpersand")
        self.verticalLayout.addWidget(self.CorrAmpersand)
        self.ICN_templateName = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.ICN_templateName.setAlignment(QtCore.Qt.AlignCenter)
        self.ICN_templateName.setObjectName("ICN_templateName")
        self.verticalLayout.addWidget(self.ICN_templateName)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Correlating ICs & ICNs"))
        self.ic_fileName.setText(_translate("Dialog", "Loading ..."))
        self.CorrAmpersand.setText(_translate("Dialog", "&"))
        self.ICN_templateName.setText(_translate("Dialog", "Loading ..."))

