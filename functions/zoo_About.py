from PyQt5.QtWidgets import QDialog, QWidget
import zoo_AboutWin as aboutwin    # PyQt widget in ../gui

class newAboutWin(QDialog, aboutwin.Ui_AboutWin):
    """Opens new window showing general info about Network Zoo program"""
    
    def __init__(self, **kwargs):
        
        super(self.__class__, self).__init__()
        
        newWin = QDialog(self)
        self.setupUi(newWin)
        
        if 'file' in kwargs.keys():
            file = kwargs['file']
            aboutText = open(file).read()
            self.textBrowser.setPlainText(aboutText)
            
        newWin.exec()