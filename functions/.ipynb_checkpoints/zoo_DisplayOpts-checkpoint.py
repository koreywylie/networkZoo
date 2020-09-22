# Python Libraries
from os.path import join as opj  # method to join strings of file paths
from string import digits
import os, sys, re, json, csv
import copy # deep copy method for dicts of dicts

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog

# Internal imports
import zoo_DisplayOptionsWin as displaywin    # PyQt widget in ../gui


class EditDisplayOptions(QDialog, displaywin.Ui_Dialog):
    """Launches window w/ display options for Network Zoo GUI's main window"""
    
    def __init__(self,
                 mp, tp, update_plots,
                 current_config=None, 
                 config_file='config.json'):
        super(self.__class__, self).__init__()
        
        self.mp = mp
        self.tp = tp
        self.mp_prev = copy.deepcopy(mp)
        self.tp_prev = copy.deepcopy(tp)
        self.update_plots = update_plots
        if current_config:
            self.config = current_config.copy()
        else:
            self.config = {}
        if 'display' not in self.config.keys():
            self.config.update({'display': {}})
        if 'mri_plots' not in self.config['display'].keys():
            self.config['display'].update({'mri_plots': {}})
        if 'time_plots' not in self.config['display'].keys():
            self.config['display'].update({'time_plots': {}})    
        self.config_file = config_file
            
        # Launch Display Options window
        newWin = QDialog(self)
        self.setupUi(newWin)
                
        # Tweak display window based on mp & tp
        self.set_displayedOpts_to_currentOpts()
        
        # Connections
        self.checkBox_ShowMappingName.stateChanged.connect(self.show_mapping_name)
        self.checkBox_ShowICAName.stateChanged.connect(self.show_ICAname)
        self.checkBox_ShowICNName.stateChanged.connect(self.show_ICNname)
        self.spinBox_TextSize.valueChanged.connect(self.change_TextSize)
        self.checkBox_ShowICNtemplate.stateChanged.connect(self.show_ICNtemplate)
        self.checkBox_ThreshICAvol.stateChanged.connect(self.thresh_ica_vol)
        self.doubleSpinBox_ICAvolThresh.valueChanged.connect(self.change_ica_thresh)
        self.pushButton_ChangeAnatomicalvol.clicked.connect(self.change_anatomical_vol)
        self.checkBox_DisplayICAtime.stateChanged.connect(self.show_ICAtime)
        self.checkBox_DisplayICAfreq.stateChanged.connect(self.show_ICAfreq)
        self.doubleSpinBox_TR.valueChanged.connect(self.change_TR)
        self.checkBox_SliceLayoutMatrix.stateChanged.connect(self.change_slice_layout)
        self.spinBox_numRows.valueChanged.connect(self.change_num_rows)
        self.spinBox_numCols.valueChanged.connect(self.change_num_cols)
        self.checkBox_ShowCrosshairs.stateChanged.connect(self.show_crosshairs)
        self.checkBox_ShowColorbar.stateChanged.connect(self.show_colorbar)
        self.checkBox_ShowLR.stateChanged.connect(self.show_LR)
        self.pushButton_SaveDisplayOptions.clicked.connect(self.save_display_opts)
        
        # Apply temporary changes to display
        apply_btn = self.buttonBox.button(QtWidgets.QDialogButtonBox.Apply)
        apply_btn.clicked.connect(self.apply_display_opts)

        # Open dialog window
        self.response = newWin.exec()
        
        # Adjust options for return
        self.mp['anat']['file'] = False # use gd['smri']['img'] vol. for main use        
        
        
    def set_displayedOpts_to_currentOpts(self):
        """Checks/unchecks GUI to match self.mp & self.tp settings"""
        self.checkBox_ShowMappingName.setChecked(self.mp['global']['show_mapping_name'])
        self.checkBox_ShowICAName.setChecked(self.mp['global']['show_ica_name'])
        self.checkBox_ShowICNName.setChecked(self.mp['global']['show_icn_name'])
        self.spinBox_TextSize.setValue(int(self.mp['global']['display_text_size']))
        self.checkBox_ShowICNtemplate.setChecked(self.mp['icn']['show_icn'])
        self.checkBox_ThreshICAvol.setChecked(self.mp['ica']['thresh_ica_vol'])
        if self.mp['ica']['ica_vol_thresh'] <= 1e-06:
            self.doubleSpinBox_ICAvolThresh.setValue(0)
        else:
            self.doubleSpinBox_ICAvolThresh.setValue(self.mp['ica']['ica_vol_thresh'])
        anat_old = None
        if os.path.exists(self.mp['anat']['file']):
            anat_old = self.mp['anat']['file']
        elif os.path.exists(self.config['smri_file']):
            anat_old = self.config['smri_file']
        if anat_old:
            self.label_CurrentAnatomicalName.setText(os.path.basename(anat_new))
        self.checkBox_DisplayICAtime.setChecked(self.tp['items']['show_time_series'])
        self.checkBox_DisplayICAfreq.setChecked(self.tp['items']['show_spectrum'])
        self.doubleSpinBox_TR.setValue(int(self.tp['global']['sampling_rate']))
        self.checkBox_SliceLayoutMatrix.setChecked(self.mp['global']['grid_layout'])
        self.spinBox_numRows.setValue(int(self.mp['global']['num_rows']))
        self.spinBox_numCols.setValue(int(self.mp['global']['num_cols']))
        if self.checkBox_SliceLayoutMatrix.isChecked():
            self.spinBox_numRows.setEnabled(True)
            self.spinBox_numCols.setEnabled(True)
            self.set_slices_to_match_grid()
        self.checkBox_ShowCrosshairs.setChecked(self.mp['global']['crosshairs'])
        self.checkBox_ShowColorbar.setChecked(self.mp['global']['show_colorbar'])
        self.checkBox_ShowLR.setChecked(self.mp['global']['show_LR_annotations'])
        
        
    def show_mapping_name(self, state):
        """Show ICA > ICN mapping name on display"""
        self.mp['global']['show_mapping_name'] = state
            
    def show_ICAname(self, state):
        """Show ICA component name on display"""
        self.mp['global']['show_ica_name'] = state
            
    def show_ICNname(self, state):
        """Show ICN template name on display"""
        self.mp['global']['show_icn_name'] = state
            
    def change_TextSize(self, size):
        """Change text size for ICs, ICNs, & mappings on display"""
        self.mp['global']['display_text_size'] = size
    
    def show_ICNtemplate(self, state):
        """Plot ICN template on display"""
        self.mp['icn']['show_icn'] = state
                                                        
    def thresh_ica_vol(self, state):
        """Threshold ICA volumes for display"""
        self.mp['ica']['thresh_ica_vol'] = state
        if state:
            self.doubleSpinBox_ICAvolThresh.setEnabled(True)
        else:
            self.doubleSpinBox_ICAvolThresh.setEnabled(False)
            
    def change_ica_thresh(self, thresh):
        """Set threshold used for ICA volumes"""
        self.mp['ica']['ica_vol_thresh'] = thresh
        
                                                             
    def change_anatomical_vol(self):
        """Temporarily change anatomical image background for plotting"""
        if self.mp['anat']['file']:
            anat_vol_old = self.mp['anat']['file']
        elif 'smri_file' in self.config.keys():
            anat_vol_old = self.config['smri_file']
        else:
            anat_vol_old = None
        f_title = 'Select anatomical MRI vol. to display in background:'
        f_dir = os.path.dirname(anat_vol_old)
        f_filter = "Image Files (*.nii.gz *.nii *.img)"
        anat_new, ok = QtWidgets.QFileDialog.getOpenFileName(self, f_title, f_dir, f_filter)
        if anat_new and ok:
            self.mp['anat']['file'] = str(anat_new) # temporary sMRI filename storage
            self.label_CurrentAnatomicalName.setText(os.path.basename(anat_new))
        else:
            title = "Error loading new anatomical MRI vol"
            message = "Cannot find new anatomical MRI vol, using currently loaded vol. for display"
            QtWidgets.QMessageBox.warning(self, title, message)
    
    
    def show_ICAtime(self, state):
        """Plot ICA time series on display"""
        self.tp['items']['show_time_series'] = state
            
    def show_ICAfreq(self, state):
        """Plot ICA frequency spectrum on display"""
        self.tp['items']['show_spectrum'] = state
        
    def change_TR(self, TR):
        """Change fMRI sampling rate TR for display"""
        self.tp['global']['sampling_rate'] = TR
        
        
    def change_slice_layout(self, state):
        """Change slice layout settings to/from linear to rectangular matrix"""
        if state:
            self.spinBox_numRows.setEnabled(True)
            self.spinBox_numCols.setEnabled(True)
            self.mp['global']['grid_layout'] = True
            
            if self.mp['global']['display_mode'] in ['ortho', 'tiled']:
                title = "Slice layout settings"
                message = 'Changes to slice layout will not be visible with current display settings.'
                message += '\n\nTemporarily change layout to "axial" slices to view full grid '
                message += 'with specified number of rows & columns?'
                if QtWidgets.QMessageBox.warning(self, title, message,
                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                 QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                    self.mp['global']['display_mode'] = 'axial'
                    self.update_plots()
        else:
            self.spinBox_numRows.setEnabled(False)
            self.spinBox_numCols.setEnabled(False)
            self.mp['global']['grid_layout'] = False
            
    def change_num_rows(self, m):
        """Change number of rows in slice matrix display"""
        self.mp['global']['num_rows'] = m
        self.set_slices_to_match_grid(m=m)
    
    def change_num_cols(self, n):
        """Change number of columns in slice matrix display"""
        self.mp['global']['num_cols'] = n
        self.set_slices_to_match_grid(n=n)
        
    def set_slices_to_match_grid(self, m=None, n=None):
        """Sets number of slices to match layout as rectangular grid"""
        m = self.spinBox_numRows.value() if m is None else m
        n = self.spinBox_numCols.value() if n is None else n
        self.mp['global']['num_slices'] = m * n
                
    def show_crosshairs(self, state):
        """Show crosshairs marking coordinates on display"""
        self.mp['global']['crosshairs'] = state
        
    def show_colorbar(self, state):
        """Show colobar on display"""
        self.mp['global']['show_colorbar'] = state
        
    def show_LR(self, state):
        """Show Left/Right indicators on display"""
        self.mp['global']['show_LR_annotations'] = state
        
    def save_display_opts(self):
        """Save current display opts. as default configuration settings"""
        self.config['display']['mri_plots'] = self.mp
        self.config['display']['time_plots'] = self.tp
        if self.mp['anat']['file']:
            self.config['smri_file'] = self.mp['anat']['file']
            self.mp['anat']['file'] = False
        self.write_configs_to_json()
        
    def apply_display_opts(self):
        """Update display w/ temporary options"""
        text = self.label_applyWarning.text()
        self.label_applyWarning.setText("(updating & re-drawing display, may take a few milliseconds...)")
        self.update_plots()
        self.label_applyWarning.setText(text)

            
    def write_configs_to_json(self):
        """Saves current configuration to default file, to read on startup"""
        
        if not hasattr(self, 'config'): return
        if 'base_directory' in self.config.keys():
            mypath = self.config['base_directory']
        elif 'mypath' in locals():
            pass
        else:
            mypath = os.getcwd()
        
        if hasattr(self, 'config_file'):
            if self.config_file:
                if os.path.isfile(self.config_file):
                    config_file = self.config_file
                elif os.path.isfile(opj(mypath, 'config_settings', self.config_file)):
                    config_file = opj(mypath, 'config_settings', self.config_file)
        if 'config_file' not in locals():
            config_file = opj(mypath, 'config_settings', 'config.json')
        if os.path.isfile(config_file):
            os.remove(config_file)                                                                     
            
        config = self.config
        with open(config_file, 'w') as json_file:
            json.dump(config, json_file)    
            
        self.changedConfigs = True
        