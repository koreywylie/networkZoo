# Python Libraries
from os.path import join as opj  # method to join strings of file paths
from string import digits
import os, sys, re, json, csv
import copy # deep copy method for dicts of dicts

# Mathematical/Neuroimaging/Plotting Libraries
import numpy as np

# Qt GUI Libraries
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog

# Internal imports
import zoo_OutputOptionsWin as outputwin    # PyQt widget in ../gui

class EditOutputOptionsGUI(QDialog, outputwin.Ui_Dialog):
    """Launches window w/ output/mask creation options & parameters for Network Zoo"""
    
    def __init__(self, config, config_file='config.json'):
        super(self.__class__, self).__init__()
        
        self.config = copy.deepcopy(config)
        self.config_file = config_file
        
        # Launch output options window
        newWin = QDialog(self)
        self.setupUi(newWin)
                
        # Connections
        self.checkBox_CreateFigure.stateChanged.connect(self.change_create_figure)
        self.checkBox_ConcatVertical.stateChanged.connect(self.change_concat_vertical)
        self.spinBox_FigRows.valueChanged.connect(self.change_figure_rows)
        self.spinBox_FigCols.valueChanged.connect(self.change_figure_cols)
        self.checkBox_CreateTable.stateChanged.connect(self.change_create_table)
        self.checkBox_ThreshICApercentile.stateChanged.connect(self.thresh_by_percentile)
        self.doubleSpinBox_ThreshPercentile.valueChanged.connect(self.change_percentile_thresh)
        self.checkBox_ThreshICAfractionOfMax.stateChanged.connect(self.thresh_by_max)
        self.doubleSpinBox_ThreshFractionMax.valueChanged.connect(self.change_fract_max_thresh)
        self.checkBox_SmoothEdges.stateChanged.connect(self.smooth_mask)
        self.pushButton_SaveOutputOptions.clicked.connect(self.save_output_opts)
        
        # Tweak display window based on self.config['masks']
        self.set_OutputOpts_to_currentOpts()

        
        # Open dialog window
        self.response = newWin.exec()
        
        
    def set_OutputOpts_to_currentOpts(self):
        """Checks/unchecks GUI to match config['masks'] settings"""
        self.checkBox_CreateFigure.setChecked(self.config['output']['create_figure'])
        self.checkBox_ConcatVertical.setChecked(self.config['output']['concat_vertical'])
        self.spinBox_FigRows.setValue(int(self.config['output']['figure_rows']))
        self.spinBox_FigCols.setValue(int(self.config['output']['figure_cols']))
        self.checkBox_ThreshICApercentile.setChecked(self.config['masks']['thresh_percentile'])
        self.doubleSpinBox_ThreshPercentile.setValue(float(self.config['masks']['cutoff_percentile']))
        self.checkBox_ThreshICAfractionOfMax.setChecked(self.config['masks']['thresh_max'])
        self.doubleSpinBox_ThreshFractionMax.setValue(float(self.config['masks']['cutoff_fractMax']))
        self.checkBox_SmoothEdges.setChecked(self.config['masks']['smooth_mask'])
        
        
    def change_create_figure(self, state):
        """Create figure of concatenated displays for classifications"""
        self.config['output']['create_figure'] = state
        if state:
            self.checkBox_ConcatVertical.setEnabled(True)
            self.spinBox_FigRows.setEnabled(True)
            self.spinBox_FigCols.setEnabled(True)
        else:
            self.checkBox_ConcatVertical.setEnabled(False)
            self.spinBox_FigRows.setEnabled(False)
            self.spinBox_FigCols.setEnabled(False)
            
    def change_concat_vertical(self, state):
        """Concat classification displays vertically vs. horizontally"""
        self.config['output']['concat_vertical'] = state

    def change_figure_rows(self, num_rows):
        """Control number of height/number of rows in concat. displays figure"""
        self.config['output']['figure_rows'] = int(num_rows)
        
    def change_figure_cols(self, num_cols):
        """Control number of width/number of columns in concat. displays figure"""
        self.config['output']['figure_cols'] = int(num_cols)
        
    def change_create_table(self, state):
        """Create .csv table of classification info"""
        self.config['output']['create_table'] = state
        
    def thresh_by_percentile(self, state):
        """Threshold mapped ICA vol. to create mask based on top percentile of voxels"""
        self.config['masks']['thresh_percentile'] = state
        if state:
            self.doubleSpinBox_ThreshPercentile.setEnabled(True)
        else:
            self.doubleSpinBox_ThreshPercentile.setEnabled(False)
        
    def change_percentile_thresh(self, thresh):
        """Change threshold percentile cutoff value used for mask creation"""
        self.config['masks']['cutoff_percentile'] = float(thresh)
        
    def thresh_by_max(self, state):
        """Threshold mapped ICA vol. to create mask based on fraction of max. abs. value"""
        self.config['masks']['thresh_max'] = state
        if state:
            self.doubleSpinBox_ThreshFractionMax.setEnabled(True)
        else:
            self.doubleSpinBox_ThreshFractionMax.setEnabled(False)
        
    def change_fract_max_thresh(self, thresh):
        """Change fraction of max value used for mask creation"""
        self.config['masks']['cutoff_fractMax'] = float(thresh)
        
    def smooth_mask(self, state):
        """Smooth edges & fill in holes in mask using nilearn function"""
        self.config['masks']['smooth_mask'] = state
        
    def save_output_opts(self):
        """Save current output opts. as default configuration settings"""
        self.write_configs_to_json()
        
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