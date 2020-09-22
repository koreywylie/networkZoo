from PyQt5.QtWidgets import QDialog, QListWidgetItem, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRectF
import zoo_SelectListWin as selectwin    # PyQt widget in ../gui

class newSelectWin(QDialog, selectwin.Ui_zoo_SelectListWin):
    """Dialog to select subset of list items to remove,
    from lists on Network Zoo GUI's main window"""
    
    def __init__(self, listWidget, **kwargs):
        
        super(self.__class__, self).__init__()
        
        newWin = QDialog(self)
        self.setupUi(newWin)
        
        if 'title' in kwargs:  # customize win. title
            title = kwargs.get('title')
        elif list_name in kwargs:
            if list_name == 'ica':
                title = 'Select ICA components:'
            elif list_name == 'icn':
                title = 'Select ICN templates :'
            else:
                title = 'Select '+list_name+':'
        else:
            title = 'Select items:'
        newWin.setWindowTitle(title)
            
        if 'extras' in kwargs:  # extra items to ignore in list
            extras = kwargs.get('extras')
        else:
            extras = None
        if 'list_subset' in kwargs: # limit selection to subset of list items
            list_subset = kwargs.get('list_subset') 
        else:
            list_subset = None
        if 'add_items' in kwargs: # additional items to add
            add_items = kwargs.get('add_items')
        else:
            add_items = None
            
            
        self.selected_lookup_names = []
        self.listWidget_toSelectFrom = listWidget
        items = [self.listWidget_toSelectFrom.item(i) 
                 for i in range(self.listWidget_toSelectFrom.count())]
        if extras:
            items = [item for item in items if item not in extras]
        if list_subset is not None:
            items = [item for item in items if item in list_subset]
        for item in items:
            self.listWidget_selection.addItem(item.clone())
        if add_items:
            for new_name in add_items:
                item = QListWidgetItem(new_name)
                self.listWidget_selection.addItem(item)
                item.setData(Qt.UserRole, new_name)
                item.setText(new_name)
        
        
        self.accept_result = newWin.exec()
        if self.listWidget_selection.currentRow() != -1:
            self.selected_lookup_names = [str(item.data(Qt.UserRole)) for item
                                          in self.listWidget_selection.selectedItems()]
            selected_display_names = [str(item.text()) for item
                                      in self.listWidget_selection.selectedItems()]
            self.selected_display_names = dict(zip(self.selected_lookup_names, 
                                                   selected_display_names))

        
        
        
        