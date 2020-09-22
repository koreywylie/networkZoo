# Python Libraries
from os.path import join as opj  # method to join strings of file paths
from string import digits
import os, sys, re, json, csv
import copy # deep copy method for dicts of dicts

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog

# Internal imports
import zoo_PreferrencesWin as prefwin    # PyQt widget in ../gui


class EditPreferrencesGUI(QDialog, prefwin.Ui_Dialog):
    """Launches window w/ preferrences' options"""
    
    def __init__(self, config, 
                 config_backup=opj('config_settings', 'config_settings_backup.py'), 
                 config_file='config.json'):
        super(self.__class__, self).__init__()
        
        self.config = copy.deepcopy(config)
        self.config_backup = config_backup
        self.config_file = config_file
        self.resetConfigs = False
        self.changedConfigs = False
            
        # Launch Preferrences window
        newWin = QDialog(self)
        self.setupUi(newWin)
        
        # Get original text in display
        self.buttonTxtICA_default = self.checkBox_LoadICAonStartup.text()
        self.buttonTxtICN_default = self.checkBox_LoadICNonStartup.text()
        self.buttonTxtNoise_default = self.checkBox_LoadNoiseOnStartup.text()
        self.buttonTxtsMRI_default = self.checkBox_LoadAnatonStartup.text()
        
        # Tweak display window based on config.json
        self.set_display_to_config()
        
        # Connections
        self.checkBox_LoadICAonStartup.clicked.connect(self.load_ICA_on_startup)
        self.checkBox_LoadICNonStartup.clicked.connect(self.load_ICN_on_startup)
        self.checkBox_LoadNoiseOnStartup.clicked.connect(self.load_noise_on_startup)
        self.checkBox_LoadAnatonStartup.clicked.connect(self.load_anat_on_startup)
        self.checkBox_AllowICAmultiClass.clicked.connect(self.allow_ica_multiClass)
        self.checkBox_CorrelateOnClick.clicked.connect(self.corr_on_click)
        self.pushButton_RestoreDefaults.clicked.connect(self.reset_to_defaults)

        # Open dialog window
        self.response = newWin.exec()

        # Save changes to self.config_file
        if self.response == QDialog.Accepted:
            self.write_configs_to_json()
            
        
    def set_display_to_config(self):
        """Checks/unchecks GUI to match self.config settings"""
        
        if self.config['ica']['directory'] == "":
            self.checkBox_LoadICAonStartup.setChecked(False)
            buttonTxt = self.buttonTxtICA_default
            self.checkBox_LoadICAonStartup.setText(buttonTxt)
        else:
            self.checkBox_LoadICAonStartup.setChecked(True)
            buttonTxt = self.buttonTxtICA_default
            buttonTxt += " (" + self.config['ica']['directory']
            buttonTxt += "/" + self.config['ica']['template'] + ")"
            self.checkBox_LoadICAonStartup.setText(buttonTxt)
        if self.config['icn']['directory'] == "":
            self.checkBox_LoadICNonStartup.setChecked(False)
            buttonTxt = self.buttonTxtICN_default
            self.checkBox_LoadICNonStartup.setText(buttonTxt)
        else:
            self.checkBox_LoadICNonStartup.setChecked(True)
            buttonTxt = self.buttonTxtICN_default
            buttonTxt += " (" + self.config['icn']['directory']
            buttonTxt += "/" + self.config['icn']['template'] + ")"
            self.checkBox_LoadICNonStartup.setText(buttonTxt)
        if self.config['noise']['directory'] == "":
            self.checkBox_LoadNoiseOnStartup.setChecked(False)
            buttonTxt = self.buttonTxtNoise_default
            self.checkBox_LoadNoiseOnStartup.setText(buttonTxt)
        else:
            self.checkBox_LoadNoiseOnStartup.setChecked(True)
            buttonTxt = self.buttonTxtNoise_default
            buttonTxt += " (" + self.config['noise']['directory']
            buttonTxt += "/" + self.config['noise']['template'] + ")"
            self.checkBox_LoadNoiseOnStartup.setText(buttonTxt)
        if self.config['smri_file'] == "":
            self.checkBox_LoadAnatonStartup.setChecked(False)
            buttonTxt = self.buttonTxtsMRI_default
            self.checkBox_LoadAnatonStartup.setText(buttonTxt)
        else:
            self.checkBox_LoadAnatonStartup.setChecked(True)
            buttonTxt = self.buttonTxtsMRI_default
            buttonTxt += " (" + self.config['smri_file'] + ")"
            self.checkBox_LoadAnatonStartup.setText(buttonTxt)
        self.checkBox_AllowICAmultiClass.setChecked(self.config['ica']['allow_multiclassifications'])
        self.checkBox_CorrelateOnClick.setChecked(self.config["corr_onClick"])

        
    def load_ICA_on_startup(self, state):
        """Sets or skips loaded ICA spatial maps on startup"""
        
        if state:
            title = "Select dir. containing new default ICA spatial maps"
            if self.config['ica']['directory']:
                default_dir = self.config['ica']['directory']
            elif 'base_directory' in self.config.keys():
                default_dir = self.config['base_directory']
            else:
                default_dir = os.getcwd()
                
            new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, title, default_dir)
            ok = True if os.path.exists(new_dir) else False
            
            if ok:
                self.config['ica']['directory'] = new_dir
                self.checkBox_LoadICAonStartup.setChecked(True)
                buttonTxt = self.buttonTxtICA_default
                buttonTxt += "  (" + self.config['ica']['directory']
                buttonTxt += "/" + self.config['ica']['template'] + ")"
                self.checkBox_LoadICAonStartup.setText(buttonTxt)
            else:
                self.checkBox_LoadICAonStartup.setChecked(False)
        else:
            self.checkBox_LoadICAonStartup.setText(self.buttonTxtICA_default)

        
    def load_ICN_on_startup(self, state):
        """Sets or skips loaded ICN templates on startup"""
        
        if state:
            title = "Select dir. containing new default ICN templates"
            if self.config['icn']['directory']:
                default_dir = self.config['icn']['directory']
            else:
                default_dir = self.config['base_directory']
            new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, title, default_dir)
            ok = True if os.path.exists(new_dir) else False
            
            if ok:
                self.config['icn']['directory'] = new_dir
                buttonTxt = self.buttonTxtICN_default
                buttonTxt += "  (" + self.config['icn']['directory']
                buttonTxt += "/" + self.config['icn']['template'] + ")"
                self.checkBox_LoadICNonStartup.setText(buttonTxt)
            else:
                self.checkBox_LoadICNonStartup.setChecked(False)
        else:
            self.checkBox_LoadICNonStartup.setText(self.buttonTxtICN_default)

        

    def load_noise_on_startup(self, state):
        """Sets or skips loaded noise templates on startup"""
        
        if state:
            title = "Select dir. containing new default noise templates (CSF, WM, etc.)"
            if self.config['noise']['directory']:
                default_dir = self.config['noise']['directory']
            else:
                default_dir = self.config['base_directory']
            
            new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, title, default_dir)
            ok = True if os.path.exists(new_dir) else False
            
            if ok:
                self.config['noise']['directory'] = new_dir
                buttonTxt = self.buttonTxtNoise_default
                buttonTxt += "  (" + self.config['noise']['directory']
                buttonTxt += "/" + self.config['noise']['template'] + ")"
                self.checkBox_LoadNoiseOnStartup.setText(buttonTxt)
            else:
                self.checkBox_LoadNoiseOnStartup.setChecked(False)
        else:
            self.checkBox_LoadNoiseOnStartup.setText(self.buttonTxtNoise_default)

            
    def load_anat_on_startup(self, state):
        """Change default anatomical image background for plotting"""
        
        if state:
            anat_vol_old = self.config['smri_file']
            f_title = 'Select anatomical MRI vol. to display in background:'
            f_dir = os.path.dirname(anat_vol_old)
            f_filter = "Image Files (*.nii.gz *.nii *.img)"
            anat_new, _ = QtWidgets.QFileDialog.getOpenFileName(self, f_title, f_dir, f_filter)
            
            ok = False
            if os.path.isfile(anat_new):
                if os.path.splitext(anat_new)[-1] in ['.img', '.hdr', '.nii']:
                    ok = True
                elif os.path.splitext(anat_new)[-1] in ['.gz']:
                    file_name2 = os.path.splitext(anat_new)[-2]
                    if os.path.splitext(file_name2)[-1] in ['.img', '.hdr', '.nii']:
                        ok = True
            if ok:
                self.config['smri_file'] = anat_new
                buttonTxt = self.buttonTxtsMRI_default
                buttonTxt += "  (" + self.config['smri_file'] + ")"
                self.checkBox_LoadAnatonStartup.setText(buttonTxt)
            else:
                self.checkBox_LoadAnatonStartup.setChecked(False)
        else:
            self.config['smri_file'] = ""
            self.checkBox_LoadAnatonStartup.setText(self.buttonTxtsMRI_default)
            
    def allow_ica_multiClass(self, state):
        """Allow non-unique classification of ICA comps.,
        where one IC can be mapped to multiple ICNs"""
        self.config['ica']['allow_multiclassifications'] = state
        

    def corr_on_click(self, state):
        """Change whether/not new ICA/ICN pairs are correlated when selected by default"""
        self.config["corr_onClick"] = True if state else False
            
        
    def reset_to_defaults(self):
        """Reset all configurations to default settings"""
        
        title = "Resetting NetworkZoo Configuration Settings"
        message = "Return configurations loaded on startup "
        message += "(i.e., ICA spatial maps, ICN templates, etc.),"
        message += " as well as modified display & output parameters, "
        message += " to default settings?"
        message += "\n\nIf Yes, click on 'Save all' to finalize & save settings"
        if QtWidgets.QMessageBox.warning(self, title, message,
                                         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
            return # do nothing
        else:
            warningFlag = False
            if self.config_backup is None:
                warningFlag = True
                message = "Backup configuration file not found!"
            elif len(self.config_backup.keys()) == 0:
                warningFlag = True
                message = "Backup configuration file is empty!"
            else:           # Check for required & optional fields, ensure backup is not unusuable
                if "output_directory" in self.config_backup.keys():
                    self.config["output_directory"] = self.config_backup["output_directory"]
                if "saved_analysis" in self.config_backup.keys():
                    self.config["saved_analysis"] = self.config_backup["saved_analysis"]
                if "corr_onClick" in self.config_backup.keys():
                    self.config["corr_onClick"] = self.config_backup["corr_onClick"]
                if set(["ica", "icn", "noise", "smri_file"]) <= set(self.config_backup.keys()):
                    self.config['ica'] = self.config_backup['ica']
                    self.config['icn'] = self.config_backup['icn']
                    self.config['noise'] = self.config_backup['noise']
                    self.config['smri_file'] = self.config_backup['smri_file']
                else:
                    warningFlag = True
                if "display" not in self.config_backup.keys():
                    warningFlag = True
                elif not (set(["mri_plots", "time_plots"]) <= 
                          set(self.config_backup["display"].keys())):
                    warningFlag = True
                elif not (set(['icn', 'ica', 'anat', 'global']) <= 
                          set(self.config_backup["display"]["mri_plots"].keys())):
                    warningFlag = True
                elif not (set(["items","global"]) <= 
                          set(self.config_backup["display"]["time_plots"].keys())):
                    warningFlag = True
                elif not (set(["show_icn","filled","alpha",
                               "levels","colors"]) <= 
                          set(self.config_backup["display"]["mri_plots"]["icn"].keys())):
                    warningFlag = True
                elif not (set(['thresh_ica_vol', 'ica_vol_thresh']) <= 
                          set(self.config_backup["display"]["mri_plots"]["ica"].keys())):
                    warningFlag = True
                elif not (set(["display_mode", "grid_layout", 
                               "num_rows", "num_cols",
                               "crosshairs",
                               "show_mapping_name","show_ica_name",
                               "show_icn_name","display_text_size"]) <=
                          set(self.config_backup["display"]["mri_plots"]["global"].keys())):
                    warningFlag = True
                elif not "sampling_rate" in self.config_backup["display"]["time_plots"]["global"].keys():
                    warningFlag = True
                elif not (set(["show_time_series","show_spectrum"]) <= 
                          set(self.config_backup["display"]["time_plots"]["items"].keys())):
                    warningFlag = True
                if 'output' not in self.config_backup.keys():
                    warningFlag = True
                elif not (set(['create_figure', 'figure_rows', 'figure_cols', 'create_table']) <=
                          set(self.config_backup['output'].keys())):
                    warningFlag = True
                if warningFlag:  
                    message = "Backup configuration file missing required fields,"
                    message += " configuration file cannot be reset."
                    message += " If problem(s) persist, networkZoo may need to be re-installed"

            self.config = self.config_backup
            if 'mypath' in locals():
                self.config['base_directory'] = mypath
            else:
                self.config['base_directory'] = os.getcwd()
            
        if warningFlag:
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            self.resetConfigs = True  # note outcome
            self.set_display_to_config()
        
        
    def write_configs_to_json(self):
        """Saves current configuration to default file, to read on startup"""
        
        if not hasattr(self, 'config'): return
        
        if not self.checkBox_LoadICAonStartup.isChecked():
            self.config['ica']['directory'] = ""
        if not self.checkBox_LoadICNonStartup.isChecked():
            self.config['icn']['directory'] = ""
        if not self.checkBox_LoadNoiseOnStartup.isChecked():
            self.config['noise']['directory'] = ""
        if not self.checkBox_LoadAnatonStartup.isChecked():
            self.config['smri_file'] = ""
        if not self.checkBox_CorrelateOnClick.isChecked():
            self.config['corr_onClick'] = False
            
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

        
                              
