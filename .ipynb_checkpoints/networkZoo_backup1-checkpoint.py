
"""
networkZoo.py
"""

# Python Libraries
from os.path import join as opj  # method to join strings of file paths
import getopt  # used to parse command-line input
import os, sys, re, json
import pickle
from functools import partial
from string import digits

# # Output imports
import csv

# Qt GUI Libraries
from PyQt5 import QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QThread, QRectF
from PyQt5.QtGui import QColor, QPixmap, QPainter


# Mathematical/Neuroimaging/Plotting Libraries
import numpy as np  # Library to for all mathematical operations
from nilearn import plotting, image, input_data  # library for neuroimaging
from nilearn import masking
from scipy.ndimage import binary_dilation #used to smooth edges of binary masks
from nibabel.nifti1 import Nifti1Image, Nifti1Pair
from nibabel.affines import apply_affine
import nipype.interfaces.io as nio
import matplotlib.pyplot as plt  # Plotting library
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure as Figure


# Set Paths for script
sys.path.append(os.getcwd())  # default location of script, path needed for "Internal imports" below
sys.path.append(opj(os.getcwd(), 'config_settings'))
sys.path.append(opj(os.getcwd(), 'functions'))
sys.path.append(opj(os.getcwd(), 'gui'))
mypath = os.getcwd()


# Internal imports
from settings import mri_plots as mp, time_plots as tp  # use items in settings file
import zoo_MainWin                # Qt GUI for pyqt5 window setup, created by Qt's 'designer' & anaconda3 fn. 'pyuic5'  
import zoo_SelectWin   as select  # Qt GUI for clickable selecting items from list
import zoo_Mapper      as map     # Qt GUI + progress bar, for numpy correlations between spatial maps
import zoo_ImageSaving as saver   # Qt GUI + progress bar, for saving display & creating concatenated output images


# Selectively suppress expected irrevelant warnings
import warnings
# warnings.filterwarnings('ignore', '.*Casting data from int32 to float32.*') #change of datatypes in nilearn
# warnings.filterwarnings('ignore', '.*Casting data from int8 to float32.*')
# warnings.filterwarnings('ignore', '.*This figure includes Axes that are not compatible.*') #imprecise tight layout in matplotlib
# warnings.filterwarnings('ignore', '.*No contour levels were found.*')  #binary ROI/ICN masks do not have contour levels when plotted in matplotlib
# warnings.filterwarnings('ignore', '.*converting a masked element to nan.*') #NaN possible in masks
# warnings.filterwarnings('ignore', '.*invalid value encountered in greater.*') #poor NaN handling in nilearn


ANATOMICAL_TO_TIMESERIES_PLOT_RATIO = 5
CONFIGURATION_FILE = 'config_settings/config.json'


class NetworkZooGUI(QtWidgets.QMainWindow, zoo_MainWin.Ui_MainWindow):
    """
    Main NetworkZoo GUI, for mapping IC spatial maps into ICN template vols
    """
    def __init__(self, configuration_file=None):
        super(self.__class__, self).__init__()  # Runs the initialization of the base classes (.QMainWindow and zoo_MainWin.UI_MainWindow)
        self.setupUi(self)  # This is defined in zoo_MainWin.py file automatically; created in QT Designer
        
        # Output & display-capture fns.
        self.output = saver.PatienceTestingGUI(self)
        
        # Data containers
        self.gd = {}  # gui data; dict of dict where gd[class][unique_name][file_path, nilearn image object]
        self.corrs = {} # dict of correlations, indexed by ic name
        self.matches = {} # dict of top matches, indexed by ic name
        
        # Configuration file defaults
        cfile = configuration_file if isinstance(configuration_file, str) else CONFIGURATION_FILE
        
        # Non-Qt display defaults
        if type(mp['global']['display_text_size']) not in (int, float, 'x-large'): 
            mp['global']['display_text_size'] = plt.rcParams['font.size'] * 1.44
        
        # Qt set-up for spatial & time data displays
        anat_sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        anat_sp.setVerticalStretch(ANATOMICAL_TO_TIMESERIES_PLOT_RATIO)
        ts_sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        ts_sp.setVerticalStretch(1)

        # figure instance to view spatial data
        self.figure_x = plt.figure()
        self.canvas_x = FigureCanvas(self.figure_x)
        self.verticalLayout_plot.addWidget(self.canvas_x)
        self.canvas_x.setSizePolicy(anat_sp)
        
        # change MNI coordinates on click
        self.canvas_x.mpl_connect('button_release_event', self.figure_x_onClick)

        # figure instance to view time & frequency data
        self.figure_t = plt.figure()
        self.canvas_t = FigureCanvas(self.figure_t)
        self.verticalLayout_plot.addWidget(self.canvas_t)
        self.canvas_t.setSizePolicy(ts_sp)

        # self.reset_display(initialize=True)
        self.reset_analysis()
        self.load_configuration(cfile) if os.path.isfile(cfile) else self.load_configuration()

        # Connections
        self.action_LoadAnalysis.triggered.connect(self.load_analysis)
        self.action_SaveAnalysis.triggered.connect(self.save_analysis)
        self.action_ResetAnalysis.triggered.connect(partial(self.reset_analysis, clear_lists=True, 
                                                            clear_display=True, warn=True))
        self.action_correlateOnClick.triggered.connect(self.change_itembyitem)
        self.action_runAnalysis.triggered.connect(self.run_analysis)
        self.action_createOutput.triggered.connect(saver.PatienceTestingGUI)
#         self.action_createOutput.triggered.connect(self.generate_output)  #7/17/2020 --kw-- moved to outside fn., to allow progress bar
        self.action_Quit.triggered.connect(self.quit_gui)
    
        self.action_LoadSettingsScript.triggered.connect(self.load_configuration)
        self.action_ResetSettings_to_default.triggered.connect(self.reset_to_defaults)  #7/20/2020 --kw-- added fn., needs to be tested
        self.action_LoadICAcomps_on_startup.triggered.connect(self.load_ICA_on_startup)   #7/20/2020 --kw--added fn., needs to be tested
        self.action_LoadICNtemplates_on_startup.triggered.connect(self.load_ICN_on_startup)   #7/20/2020 --kw-- added fn., needs to be tested
        self.action_ChangeDefaultStructuralVol.triggered.connect(partial(self.change_anat,
                                                                         save_as_default=True))  #7/20/2020 --kw-- added fn., needs to be tested
        #7/20/2020 --kw-- fn. below not currently added, prefer simmpler GUI
#         self.action_LoadNoisetemplates_on_startup.triggered.connect(self.load_noise_on_startup)    
        #7/20/2020 --kw-- fn. not currenlty added, prefer simmpler GUI
#         self.action_ChangeDefaultSettings.triggered.connect(self.change_defaults)

        self.action_LoadICAcomps.triggered.connect(self.browse_ica_files)
        self.action_RenameICAlist_select.triggered.connect(partial(self.rename_list_select,   #7/21/2020 --kw-- added fn., needs to be tested
                                                                   list_name='ica',
                                                                   listWidget=self.listWidget_ICAComponents))  
        self.action_ClearICAlist_select.triggered.connect(partial(self.clear_list_select,
                                                                  list_name='ica',
                                                                  listWidget=self.listWidget_ICAComponents))
        self.action_ClearICAlist_all.triggered.connect(partial(self.clear_list_all,
                                                               list_name='ica',
                                                               listWidget=self.listWidget_ICAComponents))
        self.action_LoadICNtemplates.triggered.connect(partial(self.browse_icn_files, append=True))
        self.action_RenameICNtemplates_select.triggered.connect(partial(self.rename_list_select,  #7/21/2020 --kw-- added fn., needs to be tested
                                                                        list_name='icn',
                                                                        listWidget=self.listWidget_ICNtemplates))
        self.action_ClearICNlist_select.triggered.connect(partial(self.clear_list_select,     #7/21/2020 --kw-- modified fn., needs to be tested
                                                                  list_name='icn',
                                                                  listWidget=self.listWidget_ICNtemplates))
        self.action_ClearICNlist_all.triggered.connect(partial(self.clear_list_all,           #7/21/2020 --kw-- modified fn., needs to be tested
                                                               list_name='icn',
                                                               listWidget=self.listWidget_ICNtemplates))
        self.action_LoadNoisetemplates.triggered.connect(self.load_noise_templates)
        
        self.action_RenameClassifications_select.triggered.connect(partial(self.rename_list_select,  #7/21/2020 --kw-- added fn., needs to be tested
                                                                   list_name='mapped',
                                                                   listWidget=self.listWidget_mappedICANetworks))
        self.action_DuplicateICA_select.triggered.connect(self.duplicate_mappedICAcomps)                         #7/20/2020 --kw-- new fn., needs to be added
        self.action_FindDuplicateICAClassifications.triggered.connect(partial(self.find_duplicate_mappings,        #7/20/2020 --kw-- new fn., needs to be added
                                                                              duplicated_name='ica')  #7/20/2020 --kw-- old fn. name: find_duplicate_ICNmappings
        self.action_FindDuplicateICNClassifications.triggered.connect(partial(self.find_duplicate_mappings,        #7/20/2020 --kw-- new fn., needs to be added
                                                                              duplicated_name='icn')  #7/20/2020 --kw-- old fn. name: find_duplicate_ICNmappings
#         self.action_FindDuplicateICNClassifications.triggered.connect(self.find_duplicate_ICNmappings)  #7/20/2020 --kw-- old fn. name: find_duplicate_ICNmappings
        self.action_FindProbableClassifications.triggered.connect(self.find_probable_classifications)   #7/20/2020 --kw-- new fn., needs to be added
        self.action_FindQuestionableClassifications.triggered.connect(self.find_questionable_classifications)   #7/20/2020 --kw-- new fn., needs to be added
        self.actionClearClassifications_select.triggered.connect(partial(self.clear_list_select,
                                                                         list_name='mapped',
                                                                         listWidget=self.listWidget_mappedICANetworks))  #7/20/20202 --kw-- needs to be added to to fn.
        self.action_ClearClassifications_all.triggered.connect(partial(self.clear_list_all,
                                                                       list_name='mapped',
                                                                       listWidget=self.listWidget_mappedICANetworks))  #7/20/2020 --kw-- modified fn., needs to be tested
#         self.action_ResetAllClassifications.triggered.connect(self.delete_all_mappedNetworks)  #7/17/2020 --kw-- renamed action, & moved functionality to clear_list_all
        
        self.action_DisplayICAtime.triggered.connect(self.show_ICAtime)
        self.action_DisplayICAfreq.triggered.connect(self.show_ICAfreq)
        self.action_ChangeTR.triggered.connect(self.change_TR)
        self.action_ChangeAnatomicalVol.triggered.connect(self.change_anat)
        self.action_ShowCrosshairs.toggled.connect(self.show_crosshairs)
        self.action_ThreshICAVol.toggled.connect(self.thresh_ica_vol)
        self.action_ShowICNTemplate.toggled.connect(self.show_ICNtemplate)
        self.action_ShowMappingName.toggled.connect(self.show_mapping_name)
        self.action_ShowICAName.toggled.connect(self.show_ICname)
        self.action_ShowICNTemplateName.toggled.connect(self.show_ICNtemplateName)
        self.action_ChangeTextSize.triggered.connect(self.change_displayText)

        self.action_ResetDisplay.triggered.connect(self.reset_display)
        self.action_SaveDisplay.triggered.connect(partial(saver.save_display, 
                                                          figure_x=self.figure_x, figure_t=self.figure_t,
                                                          fname=None))
#         self.action_SaveDisplay.triggered.connect(partial(self.save_display, fname=None))  #7/17/2020 --kw-- moved to outside fn., to allow progress bar
        
        self.action_createBinaryMasks.triggered.connect(self.create_binaryMasks)
        self.action_ShowAboutInfo.triggered.connect(self.show_about)                      #7/20/2020 --kw-- new fn., needs to be added
        self.action_ShowStepByStepTutorial.triggered.connect(self.show_tutorial)          #7/20/2020 --kw-- new fn., needs to be added
        
        self.pushButton_icaload.clicked.connect(self.browse_ica_files)
        self.pushButton_icnload.clicked.connect(partial(self.browse_icn_files, append=True))

        self.listWidget_ICAComponents.itemClicked.connect(self.update_gui_ica)
        self.listWidget_ICNtemplates.itemClicked.connect(self.update_gui_icn)
        self.listWidget_mappedICANetworks.itemClicked.connect(self.update_gui_mapping)

        self.pushButton_addNetwork.clicked.connect(self.add_mapped_network)
        self.pushButton_rmNetwork.clicked.connect(self.delete_mapped_network)
        self.pushButton_runAnalysis.clicked.connect(self.run_analysis)
        
        self.pushButton_createOutput.clicked.connect(saver.PatienceTestingGUI)
        
#         self.pushButton_createOutput.clicked.connect(self.generate_output)  #7/17/2020 --kw-- moved to outside fn., to allow progress bar









        self.pushButton_showOverlap.clicked.connect(self.update_plots)
        
        self.horizontalSlider_Xslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.horizontalSlider_Yslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.horizontalSlider_Zslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.buttonGroup_xview.buttonReleased.connect(self.update_plots)
        self.spinBox_numSlices.valueChanged.connect(self.update_plots)
        
        self.listWidget_ICAComponents.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_ICAComponents.clearSelection()
        self.listWidget_ICNtemplates.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_ICNtemplates.clearSelection()
        self.listWidget_mappedICANetworks.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_mappedICANetworks.clearSelection()
        
        self.action_DisplayICAtime.setChecked(tp['items']['show_time_GIFT'])
        self.action_DisplayICAfreq.setChecked(tp['items']['show_spectrum'])
        self.action_ShowCrosshairs.setChecked(mp['global']['crosshairs'])
        
    
    ##########################################################################
    #-------------------------------------------------
    ### Functions to set default for configuration ###
    #-------------------------------------------------
    def load_configuration(self, fname=None, load_ic_files=True):
        """Load from configuration, either from stored .json file, or re-load from stored config"""
        
        if not fname:
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 
                                                             caption="Open Input Configuration File", 
                                                             directory=".",
                                                             filter="Configuration File (*.json)")
        warning_flag, data = False, None
        if fname:
            if isinstance(fname, str):
                if os.path.exists(fname):
                    with open(fname) as json_config:
                        data = json.load(json_config)
                elif os.path.exists(opj(mypath, fname)):
                    fname = opj(mypath, fname)
                    with open(fname) as json_config:
                        data = json.load(json_config)
                else:
                    warning_flag = True
            elif isinstance(fname, dict):
                if all (key in fname.keys() for key in ['ica', 'icn', 'smri_file']):
                    data = fname
                else:
                    warning_flag = True
            elif hasattr(self, 'config'):
                warning_flag = True
                data = self.config
            else:
                warning_flag = True
        else:
            warning_flag = True
        if warning_flag:
            if not hasattr(self, 'config'):
                title = "Error starting networkZoo"
                message = "Default configuration file not found."
                message = message + "\n\n  After networkZoo opens, in the upper left corner under 'Edit' menu,"
                message = message + " use 'Load settings script' to navigate to networkZoo directory,"
                message = message + " and select 'config.json' to continue"
            else:
                title = "Error configuring networkZoo"
                message = "New configuration file not found, defaulting to current configuration settings"
            QtWidgets.QMessageBox.warning(self, title, message)

        if data:
            self.config = data
            if 'base_directory' not in self.config.keys(): self.config['base_directory'] = mypath
            if 'output_directory' not in self.config.keys():
                self.config['output_directory'] = mypath
            elif os.path.exists(opj(mypath, data['output_directory'])):
                self.config['output_directory'] = opj(mypath, data['output_directory'])
            elif os.path.exists(data['output_directory']):
                self.config['output_directory'] = data['output_directory']
            else: self.config['output_directory'] = mypath
            if 'saved_analysis' not in self.config.keys(): self.config['saved_analysis'] = False
            if os.path.exists(opj(mypath, data['smri_file'])):
                data['smri_file'] = opj(mypath, data['smri_file'])
            if os.path.exists(data['smri_file']):
                self.load_structural_file(data['smri_file'], file_type='smri')
            if load_ic_files:
                if os.path.exists(data['ica']['directory']):
                    self.find_files(data['ica']['directory'], 
                                    data['ica']['template'], data['ica']['search_pattern'],
                                    self.listWidget_ICAComponents, list_name='ica')
                elif data['ica']['directory'] == "":
                    self.action_LoadICAcomps_on_startup.setChecked(False)
                if os.path.exists(data['icn']['directory']):
                    self.find_files(data['icn']['directory'], 
                                    data['icn']['template'], data['icn']['search_pattern'],
                                    self.listWidget_ICNtemplates, 
                                    list_name='icn', extra_items=data['icn']['extra_items'])
                elif data['icn']['directory'] == "":
                    self.action_LoadICNtemplates_on_startup.setChecked(False)
                if os.path.exists(data['noise']['directory']):            
                    self.find_files(data['noise']['directory'], 
                                    data['noise']['template'], data['noise']['search_pattern'],
                                    self.listWidget_ICNtemplates, list_name='icn', 
                                    extra_items=data['noise']['extra_items'], append=True)
            if os.path.isfile(self.config['icn']['directory']):
                self.config['icn']['directory'] = os.path.dirname(self.config['icn']['directory'])
                                                                      
                                                                      
    def reset_to_defaults(self):
        """Reset all configurations to default settings"""
         
        title = "Resetting NetworkZoo Configuration Settings"
        message = "Return configurations loaded on startup (i.e., ICA spatial maps, ICN templates, etc.) to default settings?"
        if QtWidgets.QMessageBox.warning(self, title, message,
                                         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
            return # do nothing
        self.config = {
                      "output_directory": "saved_output",
                      "ica":{
                        "directory": "data_example/smith2009_ICNs/ica20.nii",
                        "template": "*",
                        "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii|\\.img)$"
                      },
                      "icn":{
                        "directory": "data_templates/icn_atlases/Yeo7",
                        "template": "*",
                        "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii)$",
                        "extra_items": ["...nontemplate_ICN"],
                        "labels_file": ""
                      },
                      "noise":{
                        "directory": "data_templates/noise_confounders",
                        "template": "*",
                        "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii)$",
                        "extra_items": ["...Noise_artifact"],
                        "discarded_icns": []
                      },
                      "smri_file": "data_templates/anatomical/MNI152_2009_template-withSkull.nii.gz"
                    }
        self.write_config_to_json()
    
                                                                      
    def load_ICA_on_startup(self, state):
        """Sets or skips loaded ICA spatial maps on startup"""
    
        if not state: #if unchecked, skip loading any components on startup
            new_dir = ""
            ok = True
        else:
            title = "Editing NetworkZoo Configuration Settings"
            message = "Load default ICA spatial maps on startup? Will save new configuration, toggle on & off to reset or change"
            if QtWidgets.QMessageBox.warning(self, title, message,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
                return # do nothing
            title = "Select dir. containing new default ICA spatial maps"
            if self.config['ica']['directory']:
                default_dir = self.config['ica']['directory']
            else:
                default_dir = self.config['base_directory']
            new_dir, ok = QtWidgets.QFileDialog.getExistingDirectory(self, title, default_dir)
        if ok:
            self.config['ica']['directory'] = new_dir
            self.write_config_to_json()
        
    def load_ICN_on_startup(self, state):
        """Sets or skips loaded ICN templates on startup"""
    
        if not state: #if unchecked, skip loading any ICN templates on startup
            new_dir = ""
            ok = True
        else:
            title = "Editing NetworkZoo Configuration Settings"
            message = "Load default ICN templates on startup? Will save new configuration, toggle on & off to reset or change"
            if QtWidgets.QMessageBox.warning(self, title, message,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
                return # do nothing
            title = "Select dir. containing new default ICN templates"
            if self.config['ica']['directory']:
                default_dir = self.config['icn']['directory']
            else:
                default_dir = self.config['base_directory']
            new_dir, ok = QtWidgets.QFileDialog.getExistingDirectory(self, title, default_dir)
        if ok:
            self.config['icn']['directory'] = new_dir
            self.write_config_to_json()                                                                    
        
    def write_config_to_json(self):
        """Saves current configuration to default file read on startup"""
                                                                                                                                    
        config_file = opj(mypath, 'config.json')
        config = self.config
        if os.path.exists(config_file):
            os.remove(config_file)                                                                     
        with open(config_file, 'w') as json_file:
            json.dump(config, json_file)                               

                                                                      
                                                                      
    #-------------------------------------------
    ### Functions related to overall display ###
    #-------------------------------------------
#7/17/2020 --kw-- fn. moved to zoo_ImageSaving.py
#     def save_display(self, fname=None, cleanup=True): 
#         """Copy current spatial maps & timeseries displays into new display & save """
        
#         if fname is None:
#             fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Display As:", 
#                                                              self.config['base_directory'],
#                                                              filter = "PNG(*.png)")
#         if fname:
#             if os.path.splitext(fname)[-1] in ['.jpeg', '.jpg', '.tiff', '.svg', '.gif']:
#                 title = "Warning"
#                 message = "Input Image Type: " + os.path.splitext(fname)[-1]
#                 message = message + "  not supported. Image will be saved as .png"
#                 QtWidgets.QMessageBox.warning(self, title, message)
#                 fname = os.path.splitext(fname)[0]
#             elif os.path.splitext(fname)[-1] == '.png':
#                 fname = os.path.splitext(fname)[0]
#             fig_pieces = []
            
#             # Save time/freq. info & spatial map, skip if time not displayed
#             if (tp['items']['show_time_GIFT'] or tp['items']['show_time_individual'] or
#                 tp['items']['show_time_average'] or tp['items']['show_spectrum'] or 
#                 tp['items']['show_time_group']):
#                 fname_t = fname + "_timePlot.png"
#                 fig_pieces.append(fname_t)
#                 self.figure_t.savefig(fname_t, format='png', pad_inches=0)
                
#                 fname_x = fname + "_spatialMap.png"
#                 fig_pieces.append(fname_x)
#                 self.figure_x.savefig(fname_x, format='png', pad_inches=0)
                
#                 fname_concat = self.concat_images(fig_pieces, fname, cleanup=cleanup)
#                 return fname_concat
            
#             else:   # Save spatial map only
#                 fname_x = fname + ".png"
#                 self.figure_x.savefig(fname_x, format='png', pad_inches=0)
#                 return fname_x

            
    def reset_display(self, initialize=False):
        """Clear Qt display & reset to default settings"""
        
        self.figure_x.clear()
        self.canvas_x.draw()
        self.figure_t.clear()
        self.canvas_t.draw()
        
        self.listWidget_ICAComponents.clearSelection()
        self.listWidget_ICAComponents.setCurrentRow(-1)
        self.listWidget_mappedICANetworks.clearSelection()
        self.listWidget_mappedICANetworks.setCurrentRow(-1)

        self.listWidget_ICNtemplates.clear()
        icn_keys = [k for k in self.gd['icn'].keys() if k not in self.config['icn']['extra_items']]
        if len(icn_keys) > 0:
            for icn_lookup in icn_keys:
                    item = QtWidgets.QListWidgetItem(icn_lookup)
                    self.listWidget_ICNtemplates.addItem(item)
                    item.setData(Qt.UserRole, icn_lookup)
                    self.gd['icn'][icn_lookup]['widget'] = item
                    item.setText(icn_lookup)
            for extra in self.config['icn']['extra_items']:
                    item = QtWidgets.QListWidgetItem(extra)
                    self.listWidget_ICNtemplates.addItem(item)
                    item.setData(Qt.UserRole, extra)
                    self.gd['icn'][icn_lookup]['widget'] = extra
                    item.setText(extra)
        self.listWidget_ICNtemplates.clearSelection()
        self.listWidget_ICNtemplates.setCurrentRow(-1)
        
    
    #---------------------------------------------------
    ### Functions triggered by GUI file menu actions ###
    #---------------------------------------------------
    def change_itembyitem(self, state):
        """Start/stop correlating item-by-item on every click"""
        pass # GUI checkbox is merely used as ref. called by code below, no action needed
        
    def show_ICAtime(self, state):
        """Plot ICA time series on display"""
        tp['items']['show_time_GIFT'] = state
        self.update_plots()
            
    def show_ICAfreq(self, state):
        """Plot ICA frequency spectrum on display"""
        tp['items']['show_spectrum'] = state
        self.update_plots()
            
    def change_TR(self):
        """Change fMRI sampling rate TR for display"""
        TR_old = tp['global']['sampling_rate']
        TR_title = "Change TR"
        TR_text = "Sampling rate (TR) controls the scale of time series & freq. plots.\n\nTR(s)."
        TR_text = TR_text + " Current TR=" + str(TR_old) + "\n\nEnter TR(s):"
        TR_new, ok = QtWidgets.QInputDialog.getDouble(self, TR_title, TR_text, 
                                                      2, 0, 600, 2)
        tp['global']['sampling_rate'] = TR_new if ok else TR_old
        self.update_plots()
            
    def change_anat(self, save_as_default=False):
        """Change anatomical image background for plotting"""
        
        if save_as_default:
            title = "Editing NetworkZoo Configuration Settings"
            message = "Load default ICA spatial maps on startup? Will save new configuration, toggle on & off to reset or change"
            if QtWidgets.QMessageBox.warning(self, title, message,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
                return # do nothing
        anat_vol_old = self.config['smri_file']
        f_title = 'Select anatomical MRI vol. to display in background:'
        f_dir = os.path.dirname(anat_vol_old)
        f_filter = "Image Files (*.nii.gz *.nii *.img)"
        anat_new, ok = QtWidgets.QFileDialog.getOpenFileName(self, f_title, f_dir, f_filter)
        if anat_new:
            self.config['smri_file'] = anat_new
            self.load_structural_file(self.config['smri_file'], file_type='smri')
            self.update_plots()
        else:
            QtWidgets.QMessageBox.warning(self, "Error loading new anatomical MRI vol",
                                          "Cannot find new anatomical MRI vol, using currently loaded vol for display")
        if save_as_default:
            self.write_config_to_json()
            
    def show_crosshairs(self, state):
        """Show crosshairs marking coordinates on display"""
        mp['global']['crosshairs'] = state
        self.update_plots()
            
    def thresh_ica_vol(self, state):
        """Threshold ICA volumes for display"""
        if state:
            f_title = 'Thresholding ICA volumes'
            f_text = 'All ICA volumes will be thresholded, based on \npercentage of max. value (entered below).'
            f_text = f_text + '\n\nTo change threshold, toggle "Threshold ICA Vol." off & on.'
            f_text = f_text + '\n\nPercentage of max.:'
            k, ok = QtWidgets.QInputDialog.getInt(self, f_title, f_text, 0, 0, 100)
            if k==0:
                mp['global']['thresh_ica_vol'] = 1e-06
                self.action_ThreshICAVol.setChecked(False)
            if ok:
                mp['global']['thresh_ica_vol'] = k/100
        else:
            mp['global']['thresh_ica_vol'] = 1e-06
        self.update_plots()
            
    def show_ICNtemplate(self, state):
        """Plot ICN template on display"""
        mp['global']['show_icn'] = state
        self.update_plots()
            
    def show_mapping_name(self, state):
        """Show ICA > ICN mapping name on display"""
        mp['global']['show_mapping_name'] = state
        self.update_plots()
            
    def show_ICname(self, state):
        """Show ICA component name on display"""
        mp['global']['show_ica_name'] = state
        self.update_plots()
            
    def show_ICNtemplateName(self, state):
        """Show ICN template name on display"""
        mp['global']['show_icn_templateName'] = state
        self.update_plots()
            
    def change_displayText(self):
        """Change text size for ICs, ICNs, & mappings on display"""
        textSize_old = mp['global']['display_text_size']
        textSize_title = "Change Font Size for Display Labels"
        textSize_text = "Text size controls the displayed font size (in points) for labels."
        textSize_text = textSize_text + " Current size=" + str(textSize_old) + "\n\nEnter new size:"
        textSize_new, ok = QtWidgets.QInputDialog.getDouble(self, textSize_title, 
                                                            textSize_text, textSize_old, 
                                                            1, 60, 1)
        mp['global']['display_text_size'] = textSize_new if ok else textSize_old
        self.update_plots()

    
    def load_structural_file(self, file_name, file_type='fmri'):
        """Load single MRI/fMRI vol, ~anatomical vol."""
        if file_name:
            self.gd.update({file_type: {'full_path': file_name, 
                                        'img': image.load_img(str(file_name))}})
            
    def load_noise_templates(self):
        """Load default noise templates"""
        for extra in self.config['noise']['extra_items']: #temporarily remove nontemplate slot from list
                item = self.listWidget_ICNtemplates.findItems(extra, Qt.MatchExactly)
                if len(item) > 0:
                    self.listWidget_ICNtemplates.takeItem(self.listWidget_ICNtemplates.row(item[0]))
        os.chdir(self.config['base_directory'])
        self.find_files(self.config['noise']['directory'], 
                        self.config['noise']['template'], 
                        self.config['noise']['search_pattern'], 
                        self.listWidget_ICNtemplates, 
                        list_name='icn', extra_items=self.config['noise']['extra_items'], append=True)  
    
    
    #--------------------------------------------
    ### Functions controlling entire analysis ###
    #--------------------------------------------
    def reset_analysis(self, clear_lists=False, clear_display=False, warn=False):
        """Reset entire analysis"""
        
        if warn:
            warn_title = "Resetting Analysis"
            message = "All currently loaded ICA files, ICN templates, and classifications will be discarded,"
            message = message + "\n\nContinue?"
            if QtWidgets.QMessageBox.warning(self, warn_title, message,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
                return # do nothing
        if clear_lists:
            self.listWidget_mappedICANetworks.clear()
            self.listWidget_ICAComponents.clear()
            self.listWidget_ICNtemplates.clear()
            self.lineEdit_ICANetwork.clear()
            self.lineEdit_mappedICANetwork.clear()
        if hasattr(self, 'mapper'): self.mapper = None
        if not hasattr(self, 'gd'):
            self.gd = {'smri': {}, 'ica': {}, 'icn': {}, 
                       'mapped': {}, 'mapped_ica': {}, 'mapped_icn': {}}
        else:
            self.gd['ica'] = {}
            self.gd['icn'] = {}
            self.gd['mapped'] = {}
            self.gd['mapped_ica'] = {}
            self.gd['mapped_icn'] = {}
        self.corrs = ()
        self.matches = {}
        if clear_display:
            self.reset_display()
        if hasattr(self, 'config'):
            self.config['saved_analysis'] = False

    def save_analysis(self):
        """Save info needed for analysis, but not loaded ICA/ICN volumes, for 'load_analysis()' fn."""
        
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Analysis As:", 
                                                         self.config['base_directory'],
                                                         filter='Saved Python files (*.p)')
        if fname is None or fname is '':
            QtWidgets.QMessageBox.warning(self, "Error saving analysis", 
                                          "Save filename not selected, analysis not saved")
        else:
            if os.path.splitext(fname)[-1] != '.p': fname = fname + '.p'
            
            title = "Note on saving analysis"
            message = "Saving to:"
            message = message + "\n  " + fname
            message = message + "\n\nOnly paths to ICA volumes & ICN templates will be saved."
            message = message + " If these files are modified or deleted,"
            message = message + " saved analysis will not load correctly"
            QtWidgets.QMessageBox.warning(self, title, message)
            
            self.config['saved_analysis'] = True

            config = self.config
            ica_files = [self.gd['ica'][lookup_key]['filepath'] for lookup_key in self.gd['ica'].keys()]
            ica_IndstoNames = {}
            for file in list(set(ica_files)): #create key for each unique file
                ica_IndstoNames[file] = {}
            for lookup_key in self.gd['ica'].keys():
                file = self.gd['ica'][lookup_key]['filepath']
                ica_IndstoNames[file].update([(self.gd['ica'][lookup_key]['vol_ind'], lookup_key)])
            ica_ts = {lookup_key : self.gd['ica'][lookup_key]['timecourse'] for lookup_key in self.gd['ica'].keys()}

            icn_files = [self.gd['icn'][lookup_key]['filepath'] for lookup_key in self.gd['icn'].keys()]
            icn_files = [f for f in icn_files if f is not None]
            icn_IndstoNames = {}
            for file in list(set(icn_files)): #create key for each unique file
                icn_IndstoNames[file] = {}
            for lookup_key in self.gd['icn'].keys():
                file = self.gd['icn'][lookup_key]['filepath']
                if file is not None:
                    icn_IndstoNames[file].update([(self.gd['icn'][lookup_key]['vol_ind'], lookup_key)])
            corr = self.corrs
#             mapper = None         # 7/16/2020 --kw-- saving entire mapper fn. deprecated, in favor of saving corr dict
#             if hasattr(self, 'mapper'):
#                 if hasattr(self.mapper, 'corr'):
#                     mapper = self.mapper.corr
#                 else:
#                     maper = self.mapper
            ica_icn_mapped = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_lookup'] for mapping_key in self.gd['mapped'].keys()}
            ica_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['ica_custom_name'] for mapping_key in self.gd['mapped'].keys()}
            icn_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_custom_name'] for mapping_key in self.gd['mapped'].keys()}
            
            save_data = (config, ica_files, ica_IndstoNames, ica_ts, 
                         icn_files, icn_IndstoNames, corr, 
                         ica_icn_mapped, ica_mapped_customNames, icn_mapped_customNames)
#             save_data = (config, ica_files, ica_IndstoNames, ica_ts, # 7/16/2020 --kw-- saving entire mapper fn. deprecated, in favor of saving corr dict
#                          icn_files, icn_IndstoNames, mapper, 
#                          ica_icn_mapped, ica_mapped_customNames, icn_mapped_customNames)
            with open(fname, 'wb') as f:
                pickle.dump(save_data, f)
        
    def load_analysis(self):
        """Load info from file created by 'save_analysis()' fn."""
        
        fname = QtWidgets.QFileDialog.getOpenFileName(self, "Select Saved Analysis file:", 
                                                      '.', 'Saved Python files (*.p)')
        if fname is None or fname[0] is '':
            title = "Error loading analysis"
            message = "No saved file selected, returning to current analysis"
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            fname = str(fname[0])
            with open(fname, 'rb') as f:
                reloaded_analysis = pickle.load(f)
            config                 = reloaded_analysis[0] # software defaults & configuration info
            ica_files              = reloaded_analysis[1] # ICA file paths
            ica_IndstoNames        = reloaded_analysis[2] # 4d Nifti indices for above ICA files
            ica_ts                 = reloaded_analysis[3] # array of IC time series
            icn_files              = reloaded_analysis[4] # ICN template file paths
            icn_IndstoNames        = reloaded_analysis[5] # 4d Nifti indices for above ICN template files
            corr                   = reloaded_analysis[6] # dict of correlations, between IC comps. & ICN templates
#             mapper                 = reloaded_analysis[6] # mapper obj. w/ correlations for each mapping  # 7/16/2020 --kw-- saving entire mapper fn. deprecated, in favor of saving corr dict
            ica_icn_mapped         = reloaded_analysis[7] # dict of ICA to ICN mappings (by files)
            ica_mapped_customNames = reloaded_analysis[8] # custom ICA names for above mappings
            icn_mapped_customNames = reloaded_analysis[9] # custom ICN names for above mappings
            
            self.reset_analysis(clear_lists=True, clear_display=True, warn=False)
            self.load_configuration(config, load_ic_files=False)
            self.add_files_to_list(self.listWidget_ICAComponents, 'ica', 
                                   ica_files, file_inds=ica_IndstoNames,
                                   search_pattern=self.config['ica']['search_pattern'], 
                                   append=False)
            for lookup_key,ts in ica_ts.items():
                self.gd['ica'][lookup_key]['timecourse'] = ts
            self.add_files_to_list(self.listWidget_ICNtemplates, 'icn', 
                                   icn_files, file_inds=icn_IndstoNames,
                                   search_pattern=self.config['icn']['search_pattern'],
                                   extra_items=self.config['icn']['extra_items'] + self.config['noise']['extra_items'],
                                   append=False)
            if corr is not None:
                self.corrs = corr
#             if mapper is not None:   # 7/16/2020 --kw-- saving entire mapper fn. deprecated, in favor of saving corr dict
#                 if isinstance(mapper, map.Mapper):
#                     self.mapper = mapper
#                 elif isinstance(mapper, dict):
#                     self.mapper = map.Mapper(map_files=self.get_imgobjects('icn'),
#                                              map_filenames=self.get_imgobjNames('icn'),
#                                              in_files=self.get_imgobjects('ica'),
#                                              in_filenames=self.get_imgobjNames('ica'))
#                     self.mapper.corr = mapper
            for ica_lookup, icn_lookup in ica_icn_mapped.items():
                self.add_mapped_network(ica_icn_pair=(ica_lookup, icn_lookup),
                                        ica_custom_name=ica_mapped_customNames[ica_lookup],
                                        icn_custom_name=icn_mapped_customNames[ica_lookup], updateGUI=False)
            if len(ica_icn_mapped) > 0:
                self.listWidget_mappedICANetworks.setCurrentRow(0)
                self.update_gui_mapping(self.listWidget_mappedICANetworks.currentItem())
            self.update_plots()
            
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    def run_analysis(self):
        """Run correlation analysis for all loaded ICs & ICNs"""
        
        btn_txt = self.pushButton_runAnalysis.text()
        self.pushButton_runAnalysis.setText("Correlating...")
        run_analysisGoFlag = False
        if len(self.gd['ica']) == 0: self.browse_ica_files()
        if len(self.gd['icn']) == 0: self.browse_icn_files()
        if len(self.gd['ica']) == 0 or len(self.gd['icn']) == 0:
            title = "Error Running Analysis"
            message = "Cannot start correlation analysis."
            if len(self.gd['ica']) == 0:
                message = message + " No ICA spatial maps loaded."
            if len(self.gd['icn']) == 0:
                message = message + " No ICN templates loaded."
            QtWidgets.QMessageBox.warning(self, title, message)
            self.pushButton_runAnalysis.setText(btn_txt)
            return
        
#         if not self.config['saved_analysis']: #7/17/2020 --kw-- not really needed, if mapping can be started/stopped as needed
#             if QtWidgets.QMessageBox.question(None, '', 
#                                               "Save current analysis before correlating ICs & ICNs?",
#                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
#                                               QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
#                 self.save_analysis()
#         if len(self.gd['ica']) * len(self.gd['icn']) > 1000:
#             messageBox_flag = True
#             title = "Run Correlation Analysis?"
#             message = "Calculating correlations between all pairs of current ICs & ICNs"
#             message = message + " may be computationally intensive, if either or both lists are extensive."
#             message = message + "\n\nContinue?"
#         else:
#             messageBox_flag = False
#             run_analysisGoFlag = True
#         if messageBox_flag:
#             if QtWidgets.QMessageBox.question(None, title, message,
#                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
#                                               QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
#                 run_analysisGoFlag = True
#         if run_analysisGoFlag:
            
            
            
            
            
        #testmark00000000000000000000000000000000

        ### Call GUI for progress bar ###
        self.prbrGUI = map.PatienceTestingGUI(map_files=self.get_imgobjects('icn'), 
                                              map_filenames=self.get_imgobjNames('icn'), 
                                              in_files=self.get_imgobjects('ica'), 
                                              in_filenames=self.get_imgobjNames('ica'),
                                              self.corrs)
        ### Update existing Correlations ###
        for ica_lookup in self.prbrGUI.mapper.new_corrs.keys():
            if ica_lookup not in self.corrs.keys():
                    self.corrs[ica_lookup] = {}
            self.corrs[ica_lookup].update(self.prbrGUI.mapper.new_corrs[ica_lookup])
        
        
        
        
#         self.matches = map.assign_matches(self.corrs.keys(), self.corrs)  # 7/17/2020 --kw-- likely move to menu action, under new menu "Mappings", "Find uncontested mappings", along w/ "Find debatable mappings" & fns. to re-name custom names in mapping (latter also helpful to add as list multiselection to ICs & ICNs under "Networks" menu, deselecting ICA & ICAMapped list to display ICN template during process)
            
#             self.mapper = self.prbrGUI.mapper # link to output 
            
            
            
            # self.prbrGUI.show()
            
#             import pdb; pdb.set_trace()
            
            # self.prbrGUI.mapper.run() # 7/11/2020 --kw-- works!
            # self.prbrGUI.patienceMeter.mapper.run() # 7/11/2020 --kw-- works!
            
#             self.prbrGUI = map.PatienceTestingGUI(self,
#                                                   map_files=self.get_imgobjects('icn'), 
#                                                   map_filenames=self.get_imgobjNames('icn'), 
#                                                   in_files=self.get_imgobjects('ica'), 
#                                                   in_filenames=self.get_imgobjNames('ica'))
            
#             ### Progress bar GUI ###
#             self.progress = map.Patience
#             self.progress.launch_wait_bar(self)
            
#             ### Correlation fns. ###            
#             self.mapper = map.Mapper(map_files=self.get_imgobjects('icn'), 
#                                      map_filenames=self.get_imgobjNames('icn'), 
#                                      in_files=self.get_imgobjects('ica'), 
#                                      in_filenames=self.get_imgobjNames('ica'))
            # self.mapper.run()
    
#             if not self.mapper.stopMapper: self.config['computed_analysis'] = True

#         ### Automatically add obvious & undisputed matches to mappings ###
#         for ica_lookup, icn_lookup in self.matches.items():                    #7/21/2020 --kw-- functionality implemented as menu item, not automatic
#             if ica_lookup not in self.gd['mapped_ica'].keys() and icn_lookup is not None:  #7/17/2020 --kw-- assumes single mapping per IC...
#                 self.add_mapped_network(ica_icn_pair=(ica_lookup, icn_lookup), 
#                                         ica_custom_name=ica_lookup, icn_custom_name=icn_lookup, 
#                                         updateGUI=False)     
        if self.listWidget_mappedICANetworks.count():
            self.listWidget_mappedICANetworks.setCurrentRow(0)
            mapped_item = self.listWidget_mappedICANetworks.currentItem()
            self.update_gui_mapping(mapped_item)
        else:
            self.listWidget_ICAComponents.setCurrentRow(0)
            ica_item = self.listWidget_ICAComponents.currentItem()
            self.update_gui_ica(ica_item)
        self.pushButton_runAnalysis.setText(btn_txt)
        


        
        
        
    

    #------------------------------------------------------
    ### Functions to get items from GUI data containers ###
    #------------------------------------------------------
    def get_imgobjects(self, list_name):
        """Select MRI/fMRI vols. from list"""
        return [img for img in self.get_guiitem(list_name, 'img') if isinstance(img, (Nifti1Image, Nifti1Pair))]
    
    def get_imgobjNames(self, list_name):
        """Get names for MRI/fMRI vols. in list"""
        imgs = [True if isinstance(img, (Nifti1Image, Nifti1Pair)) else False for img in self.get_guiitem(list_name, 'img')]
        names_all = [name for name in self.get_guiitem(list_name, 'name')]
        names = []
        for i, name in enumerate(names_all):
            if imgs[i]:
                names.append(name)
        return(names)
    
    def get_guiitem(self, list_name, prop):
        """Select items from networkZoo list"""
        return [v[prop] for v in self.gd[list_name].values()]
 

    #-------------------------------------------------------------------
    ### Functions to handle GUI behavior when a list item is clicked ###
    #-------------------------------------------------------------------
    def update_gui_ica(self, ica_item):       #7/15/2020 --kw-- fn. needs to be debugged & tested
        """Update plotting & selection when clicking on ICA list"""
        
        # Get current IC & ICN names
        ica_lookup = str(ica_item.data(Qt.UserRole))
        if self.listWidget_mappedICANetworks.currentRow() != -1:
            mapping_lookup = str(self.listWidget_mappedICANetworks.currentItem().data(Qt.UserRole))
            icn_lookup = str(self.gd['mapped'][mapping_lookup]['icn_lookup'])
        elif self.listWidget_ICNtemplates.currentRow() != -1:
            mapping_lookup = None
            icn_lookup = str(self.listWidget_ICNtemplates.currentItem().data(Qt.UserRole))
        else:
            mapping_lookup = None
            icn_lookup = None
        
        # Check if IC & ICN are a paired mapping
        map_itemWidget = None
        if ((icn_lookup is not None) and (mapping_lookup is None) and
            (icn_lookup in self.gd['mapped_ica'][ica_lookup].keys()):
                map_itemWidget = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
        
        # Add IC/ICN pair to corr., if needed
        self.map_one(ica_lookup, icn_lookup)
        
        # Clear & re-populate list w/ ICNs ranked
        self.repopulate_ICNs(ica_lookup)
        
        # Clear other lists & set default placement(s)
        if icn_lookup is None: #if no ICN is currently selected...
            self.listWidget_ICNtemplates.setCurrentRow(-1)
        if mapping_lookup is None:
            self.listWidget_mappedICANetworks.setCurrentRow(-1)
        elif map_itemWidget is not None:
            self.listWidget_mappedICANetworks.setCurrentItem(map_itemWidget)
            
        # Update GUI
        self.lineEdit_ICANetwork.setText(self.gd['ica'][ica_lookup]['name'])
        self.update_plots()

                
    def update_gui_icn(self, icn_item):
        """Update plotting & selection when clicking on ICN list"""
        
        # Get current IC & ICN names
        icn_lookup = str(icn_item.data(Qt.UserRole))
        if self.listWidget_mappedICANetworks.currentRow() != -1:
            mapping_lookup = str(self.listWidget_mappedICANetworks.currentItem().data(Qt.UserRole))
            ica_lookup = str(self.gd['mapped'][mapping_lookup]['ica_lookup'])
        elif self.listWidget_ICAComponents.currentRow() != -1:
            mapping_lookup = None
            ica_lookup = str(self.listWidget_ICAComponents.currentItem().data(Qt.UserRole))
        else:
            mapping_lookup = None
            ica_lookup = None
            
        # Check if IC & ICN are a paired mapping
        map_itemWidget = None
        if ((ica_lookup is not None) and (mapping_lookup is None) and
            (ica_lookup in self.gd['mapped_icn'][icn_lookup])):
                map_itemWidget = self.gd['mapped_icn'][icn_lookup][ica_lookup]
                mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
        
        # Add IC/ICN pair to corr., if needed
        self.map_one(ica_lookup, icn_lookup)
        
        # Clear other lists & set default placement(s)
        if ica_lookup is None: #if no ICN is currently selected...
            self.listWidget_ICNtemplates.setCurrentRow(-1)
        if mapping_lookup is None:
            self.listWidget_mappedICANetworks.setCurrentRow(-1)
        elif map_itemWidget is not None:
            self.listWidget_mappedICANetworks.setCurrentItem(map_itemWidget)
        
        # Update GUI
        self.lineEdit_mappedICANetwork.setText(self.gd['icn'][icn_lookup]['name'])                                 
        self.update_plots()
    

    def update_gui_mapping(self, mapping_item):
        """Update plotting & selection when clicking on mapped ICA > ICN list"""
        
        # Get current IC & ICN names
        mapping_lookup = str(mapping_item.data(Qt.UserRole))
        mapping_ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
        mapping_icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
        
        # Add IC/ICN pair to corr., if needed
        self.map_one(mapping_ica_lookup, mapping_icn_lookup)
        
        # Clear & re-populate list w/ ICNs ranked
        self.repopulate_ICNs(mapping_ica_lookup)
        
        # Set IC selection
        if mapping_ica_lookup and (mapping_ica_lookup in self.gd['ica'].keys()):
            mapped_ica_item = self.gd['ica'][mapping_ica_lookup]['widget']:
        if mapped_ica_item:
            self.listWidget_ICAComponents.setCurrentItem(mapped_ica_item)
        else:
            self.listWidget_ICAComponents.setCurrentRow(-1)
        
        # Set ICN selection
        if mapping_icn_lookup and (mapping_icn_lookup in self.gd['icn'].keys()):
            mapped_ica_item = self.gd['ica'][mapping_ica_lookup]['widget']:
        if mapped_icn_item:
            self.listWidget_ICNtemplates.setCurrentItem(mapped_icn_item)
        else:
            self.listWidget_ICNtemplates.setCurrentRow(-1)
        
        # Update GUI
        self.lineEdit_ICANetwork.setText(self.gd['mapped'][mapping_lookup]['ica_custom_name'])
        self.lineEdit_mappedICANetwork.setText(self.gd['mapped'][mapping_lookup]['icn_custom_name'])
        self.update_plots()
        
#         # Set IC selection
#         self.listWidget_ICAComponents.clearSelection()
#         self.listWidget_ICAComponents.setCurrentRow(-1)
        


#         if (self.config['computed_analysis']):
#             self.listWidget_ICNtemplates.clear() #clear & re-populate list w/ ICNs ranked
#             if ica_lookup not in self.mapper.corr.keys():
#                 self.mapper.run_one(self.gd['ica'][ica_lookup]['img'], ica_lookup)
#             for icn_lookup in self.gd['icn'].keys():
#                 if icn_lookup not in self.mapper.corr[ica_lookup].keys():
#                     if self.gd['icn'][icn_lookup]['img']:
#                         self.mapper.run_one(self.gd['ica'][ica_lookup]['img'], ica_lookup,
#                                             self.gd['icn'][icn_lookup]['img'], icn_lookup)
#             for icn_lookup, ica_corr in sorted(self.mapper.corr[ica_lookup].items(), 
#                                                key=lambda x: x[1], reverse=True):
#                 item = QtWidgets.QListWidgetItem(icn_lookup)
#                 self.listWidget_ICNtemplates.addItem(item)
#                 item.setData(Qt.UserRole, icn_lookup)
#                 if icn_lookup == mapping_icn_lookup:
#                     rank = '>'
#                     mapped_icn_item = item
#                 else:
#                     rank = ''
#                 text = '%s.  %s   (%0.2f)' %(rank, icn_lookup, 
#                                              self.mapper.corr[ica_lookup][icn_lookup])
#                 item.setText(text)
#                 self.gd['icn'][icn_lookup]['widget'] = item
#             for extra in self.config['icn']['extra_items'] + self.config['noise']['extra_items']:
#                 item = QtWidgets.QListWidgetItem(extra)
#                 self.listWidget_ICNtemplates.addItem(item)
#                 item.setData(Qt.UserRole, extra)
#                 if extra == mapping_icn_lookup:
#                     rank = '>'
#                     mapped_icn_item = item
#                     text = '%s.  %s' %(rank, mapping_icn_lookup)
#                 else:
#                     rank = ''
#                     text = '%s.  %s' %(rank, extra)
#                 item.setText(text)
#                 if extra in self.gd['icn'].keys():
#                     self.gd['icn'][extra]['widget'] = item
#         else: mapped_icn_item = None
#         if mapped_icn_item:
#             self.listWidget_ICNtemplates.setCurrentItem(mapped_icn_item)
#         else:
#             self.listWidget_ICNtemplates.setCurrentRow(0)
#         self.lineEdit_ICANetwork.setText(self.gd['mapped'][mapping_lookup]['ica_custom_name'])
#         self.lineEdit_mappedICANetwork.setText(self.gd['mapped'][mapping_lookup]['icn_custom_name'])
#         self.update_plots()

    def verify_existence(self, list_name, list_lookup=None, list_property='img'):
        """Checks for property (~spatial map/volume) in GUI data containers"""
        verdict = False
        if not list_lookup: return(verdict) #simplifies handling of None type
        if list_lookup in self.gd[list_name].keys():
            if list_property in elf.gd[list_name][list_lookup].keys():
                if self.gd[list_name][list_lookup][list_property]:
                    verdict = True
        return(verdict)   
        
    def map_one(self, ica_lookup=None, icn_lookup=None):
        """Correlate single pair of IC spatial & ICN template"""
        
        if not self.action_correlateOnClick.isChecked():
            return #nothing to do
        
        ica_imgLoaded = self.verify_existence('ica', ica_lookup)
        icn_imgLoaded = self.verify_existence('icn', icn_lookup)
        if ica_imgLoaded and (ica_lookup not in self.corrs.keys()):
            self.corrs.update({ica_lookup : })
        if icn_imgLoaded and (icn_lookup not in self.corrs[ica_lookup].keys()):
            new_corr = self.mapper.run_one(self.gd['ica'][ica_lookup]['img'], ica_lookup,
                                           self.gd['icn'][icn_lookup]['img'], icn_lookup) #7/15/2020 --kw-- modified functionality
            self.corrs.update({ica_lookup: {icn_lookup : new_corr}})        

    def repopulate_ICNs(self, ica_lookup=None):
        """Clear ICN list & re-populate w/ ranked items"""

        if not ica_lookup: return #nothing to do
        rank = 0
        for icn_lookup, ica_corr in sorted(self.corrs[ica_lookup].items(),
                                          key=lambda x x[1], reverser=True):
            if icn_lookup and ica_corr:
                rank = rank+1
                item = QtWidgets.QListWidgetItem(icn_lookup)
                self.listWidget_ICNtemplates.addItem(item)
                item.setData(Qt.UserRole, icn_lookup)
                text = '%s.  %s   (%0.2f)' %(rank, self.gd['icn'][icn_lookup]['name'], 
                                             self.corrs[ica_lookup][icn_lookup])
                item.setText(text)
                self.gd['icn'][icn_lookup]['widget'] = item
        # Add slots for non-ranked, non-corr. ICNs
        nonCorr_icns = [icn_lookup for icn_lookup in self.gd['icn'].keys() if 
                       icn_lookup not in self.corrs[ica_lookup].keys()]
        for icn_lookup in nonCorr_icns:
            item = QtWidgets.QListWidgetItem(icn_lookup)
            self.listWidget_ICNtemplates.addItem(item)
            item.setData(Qt.UserRole, icn_lookup)
            item.setText(self.gd['icn'][icn_lookup]['name'])
            self.gd['icn'][icn_lookup]['widget'] = item    
        # Add slots for non-ranked, non-corr. noise templates, Non-template ICNs, etc.
        nonCorr_extras = [icn_lookup for icn_lookup in self.config['icn']['extra_items']]
        nonCorr_extras = nonCorr_extras + [icn_lookup for icn_lookup in self.config['noise']['extra_items']]
        nonCorr_extras = [extra for extra in nonCorr_extras if extra not in self.corrs[ica_lookup].keys()]
        for extra in nonCorr_extras:
#         for extra in self.config['icn']['extra_items'] + self.config['noise']['extra_items']:  #7/16/2020 --kw-- debugging
            item = QtWidgets.QListWidgetItem(extra)
            self.listWidget_ICNtemplates.addItem(item)
            item.setData(Qt.UserRole, extra)
            if extra in self.gd['icn'].keys():
                self.gd['icn'][extra]['widget'] = item


    
    #---------------------------------------------------
    ### Functions to handle mapped IC > ICN mappings ###
    #---------------------------------------------------
    def add_mapped_network(self, ica_icn_pair=None, ica_custom_name=None, 
                           icn_custom_name=None, updateGUI=True):
        """Add ICA > ICN mapping to Qt list"""
        
        if (ica_icn_pair is None) or (ica_icn_pair is False):
            ica_lookup, icn_lookup = self.get_current_networks()
        elif len(ica_icn_pair) == 2:
            ica_lookup, icn_lookup = ica_icn_pair
        else:
            ica_lookup, icn_lookup = self.get_current_networks()
        
        if ica_custom_name is None: ica_custom_name = self.lineEdit_ICANetwork.text()
        if icn_custom_name is None: icn_custom_name = self.lineEdit_mappedICANetwork.text()
        mapping_lookup = "%s > %s" %(ica_custom_name, icn_custom_name)
        
        # Create new mapping/update existing mapping
        if (ica_lookup and icn_lookup and 
            (ica_lookup in self.gd['mapped_ica'].keys()) and 
            (icn_lookup in self.gd['mapped_ica'][ica_lookup].keys())):
            # Update existing mapping; get row in mapped listWidget & overwrite w/ new label
            map_itemWidget = self.gd['mapped_ica'][ica_lookup][icn_lookup]
            old_mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
            del self.gd['mapped'][old_mapping_lookup]
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            map_itemWidget.setText(mapping_lookup)
            
        elif ica_lookup:
            # Add new mapping to mapped listWidget
            map_itemWidget = QtWidgets.QListWidgetItem(mapping_lookup)
            self.listWidget_mappedICANetworks.addItem(map_itemWidget)
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            
            # Remove ICA item from ICA listwidget (but not in gd['ica'])
            ica_item = self.listWidget_ICAComponents.findItems(ica_lookup, Qt.MatchExactly)[0]  
            self.listWidget_ICAComponents.takeItem(self.listWidget_ICAComponents.row(ica_item))

#7/17/2020 --kw-- override code below, in order to allow ICs mapped onto multiple ICNs
#         if ica_lookup is not None and ica_lookup not in self.gd['mapped_ica'].keys():  # not yet mapped by user
#             map_itemWidget = QtWidgets.QListWidgetItem(mapping_lookup)
#             self.listWidget_mappedICANetworks.addItem(map_itemWidget)
#             map_itemWidget.setData(Qt.UserRole, mapping_lookup)
#             # remove ICA item from listwidget (but not in gd['ica'])
#             ica_item = self.listWidget_ICAComponents.findItems(ica_lookup, Qt.MatchExactly)[0]  
#             self.listWidget_ICAComponents.takeItem(self.listWidget_ICAComponents.row(ica_item))
#         elif ica_lookup is not None:  # overwrite existing mapping; get row in mapped listWidget, overwrite the label
#             map_itemWidget = self.gd['mapped_ica'][ica_lookup]
#             old_mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
#             del self.gd['mapped'][old_mapping_lookup]
#             map_itemWidget.setData(Qt.UserRole, mapping_lookup)
#             map_itemWidget.setText(mapping_lookup)
        elif icn_lookup: 
            # Create new empty mapping to ICN mask, for visualization purposes
            map_itemWidget = QtWidgets.QListWidgetItem(mapping_lookup)
            self.listWidget_mappedICANetworks.addItem(map_itemWidget)
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            
        else: return #nothing selected, nothing to do
        
        self.gd['mapped'].update({mapping_lookup: {'ica_lookup': ica_lookup,
                                                   'ica_custom_name': ica_custom_name,
                                                   'icn_lookup': icn_lookup,
                                                   'icn_custom_name': icn_custom_name,
                                                   'mapped_item' : map_itemWidget, }})
        # Link widget items to mapped ICs/ICNs
        if ica_lookup:
            if ica_lookup not in self.gd['mapped_ica'].keys():
                self.gd['mapped_ica'].update({ica_lookup : {}})
            if icn_lookup:
                self.gd['mapped_ica'][ica_lookup].update({icn_lookup : map_itemWidget})
            else:
                self.gd['mapped_ica'][ica_lookup].update({'template' : map_itemWidget})
        if icn_lookup:
            if icn_lookup not in self.gd['mapped_icn'].keys():
                self.gd['mapped_icn'].update({icn_lookup : {}})
            if ica_lookup:
                self.gd['mapped_icn'][icn_lookup].update({ica_lookup : map_itemWidget})
            else:
                self.gd['mapped_icn'][icn_lookup].update({'template' : map_itemWidget})
        if updateGUI:
            self.listWidget_ICAComponents.clearSelection()
            self.listWidget_mappedICANetworks.setCurrentItem(map_itemWidget)
            self.update_gui_mapping(map_itemWidget)
            
        
    def delete_mapped_network(self):
        """Remove ICA > ICN mapping from list"""
        
        for item in self.listWidget_mappedICANetworks.selectedItems():
            mapping_lookup = str(item.data(Qt.UserRole))
            ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
            icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
            
            # Remove mapped widget item
            self.listWidget_mappedICANetworks.takeItem(self.listWidget_mappedICANetworks.row(item))
            self.listWidget_mappedICANetworks.clearSelection()
            
            # Remove data storage for mapping
            self.gd['mapped'].pop(mapping_lookup)
            # del self.gd['mapped'][mapping_lookup]  #7/21/2020 --kw-- modified for consistency w/ other code

            # Update dict of mapped ICs/ICNs
            if icn_lookup in self.gd['mapped_ica'][icn_lookup].keys():
                self.gd['mapped_ica'][ica_lookup].pop(icn_lookup)
            if len(self.gd['mapped_ica'][ica_lookup].keys() == 0:
                self.gd['mapped_ica'].pop(ica_lookup)
            if ica_lookup in self.gd['mapped_icn'][icn_lookup].keys():
                self.gd['mapped_icn'][icn_lookup].pop(ica_lookup)
            if len(self.gd['mapped_icn'][icn_lookup].keys() == 0:
                self.gd['mapped_icn'].pop(icn_lookup)
#                 self.gd['mapped_icn'][icn_lookup].remove(ica_lookup)   #7/17/2020 --kw-- changed structure of list to dict
#                 if not self.gd['mapped_icn'][icn_lookup]: #if list is empty
#                     self.gd['mapped_icn'].pop(icn_lookup)
            
            # Add ICA item back to listwidget
            if ica_lookup in self.gd['ica'].keys():
                ica_item = QtWidgets.QListWidgetItem(ica_lookup)  # 
                self.listWidget_ICAComponents.addItem(ica_item)
                ica_item.setData(Qt.UserRole, ica_lookup)
                self.gd['ica'][ica_lookup]['widget'] = ica_item
            
                self.listWidget_ICAComponents.setCurrentItem(ica_item)
                self.update_gui_ica(ica_item)
            else:
                self.update_plots()
            
#     def delete_all_mappedNetworks(self):    #7/20/2020 --kw-- folded functionality into clear_list_all b
#         """Remove all ICA > ICN mappings from list"""
        
#         title = "Reseting all ICN classifications:"
#         message = "Reset all current 'ICA > ICN classifications' (lower list), and return ICA components to original list (upper & left)?"
#         if QtWidgets.QMessageBox.question(None, title, message,
#                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
#                                           QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
#             self.listWidget_mappedICANetworks.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
#             self.listWidget_mappedICANetworks.selectAll()
#             self.delete_mapped_network() #acts on all selected items
#             self.listWidget_mappedICANetworks.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
#             self.update_plots()
            
        
    def find_duplicate_ICNmappings(self):
        """Find ICNs mapped to multiple ICA components"""
        
        mapping_lookups = []
        icn_custom_names = []
        mappings_dup =[]
        for ind in range(self.listWidget_mappedICANetworks.count()):
            item = self.listWidget_mappedICANetworks.item(ind)
            mapping_lookup = str(item.data(Qt.UserRole))
            mapping_lookups.append(mapping_lookup)
            icn_custom_names.append(self.gd['mapped'][mapping_lookup]['icn_custom_name'])
        for ind,name in enumerate(icn_custom_names):
            if not re.match('\\.*noise', name, flags=re.IGNORECASE):
                if icn_custom_names.count(name) > 1:
                    mappings_dup.append(mapping_lookups[ind])
        if len(mappings_dup) == 0:
            title = "Searching for Duplicate ICN classifications:"
            message = "No duplicate mappings found, all current ICA names are unique"
            QtWidgets.QMessageBox.information(self, title, message)
        else:
            self.listWidget_mappedICANetworks.clearSelection()
            self.listWidget_mappedICANetworks.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
            for mapping in mappings_dup:
                item = self.gd['mapped'][mapping]['mapped_item']
                item.setSelected(True)
            title = "Searching for Duplicate ICN classifications:"
            message = "Found duplicate mappings of ICAs to identical ICNs:\n"
            for i,mapping in enumerate(mappings_dup):
                message = message + "\n   " + mapping
            message = message + "\n\nReset & re-classify above ICNs?"
            if QtWidgets.QMessageBox.question(None, title, message,
                                              QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                              QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                self.delete_mapped_network()
            self.listWidget_mappedICANetworks.clearSelection()
            self.listWidget_mappedICANetworks.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.update_plots()


    def browse_ica_files(self, append=True):
        """File browser to select & load ICA files"""
        
        if os.path.exists(self.config['ica']['directory']):
            ica_dir = self.config['ica']['directory']
        else:
            ica_dir = self.config['base_directory']
        ica_files = self.browse_files(title='Select ICA Component File(s):', directory=ica_dir,
                                      filter="Image Files (*.nii.gz *.nii *.img)")
        if ica_files: #skip reset if no new ICA files are specified
            if len(ica_files) == 1:
                ica_dir = os.path.dirname(ica_files[0])
            else:
                ica_dir = os.path.commonpath(ica_files)
            self.add_files_to_list(self.listWidget_ICAComponents, 'ica', ica_files,
                                   search_pattern=self.config['ica']['search_pattern'],
                                   exclude_pattern='(timecourses|timeseries)', append=append)
            self.load_ica_timeseries(ica_files)
            

    def load_ica_timeseries(self, ica_files, k=None, lookup_key=None):
        """Load ICA timeseries"""
        
        ica_ts = None
        r = re.compile("(timecourses|timeseries)" + self.config['ica']['search_pattern'])
        if len([f for f in filter(r.search, ica_files)]) is 1: #first, try to find time courses in ica files...
            ts_file = [f for f in filter(r.search, ica_files)]  
        elif len([f for f in filter(r.search, [ica_files[0].replace('mean_component', 'mean_timecourses')])]) is 1:
            ts_file = [f for f in filter(r.search, [ica_files[0].replace('mean_component', 'mean_timecourses')])]
        else:
            ts_file = []
            if QtWidgets.QMessageBox.question(None, '', "Are ICA time courses saved in a separate file?",
                                              QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                              QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                ts_file = self.browse_files(title='Select ICA Timecourse file:',
                                            directory=ica_dir, 
                                            filter='Timecourse saved as (*.nii.gz *.nii *.img)')
        if len(ts_file) == 0:
            ts_file = None
            tp['items']['show_time_GIFT'] = False
        if ts_file is not None:
            ts_file = ts_file[0]
            if not os.path.isfile(ts_file):  # try to find ts file in ica_dir...
                ds = nio.DataGrabber(base_directory=ica_dir, 
                                     template=self.config['ica']['template'], sort_filelist=True)
                all_nifti_files = ds.run().outputs.outfiles
                r = re.compile("(timecourses|timeseries)" + self.config['ica']['search_pattern'])
                filtered_files = [f for f in filter(r.search, all_nifti_files)]
                #    separate out ICA time series if input from spatial maps:
                ts_file = [f for f in filtered_files if 'time' in f]
                if os.path.isfile(ts_file[0]):
                    ica_ts = image.load_img(ts_file[0]).get_fdata()
            else:
                ica_ts = image.load_img(ts_file).get_fdata()

        if k:
            if ica_ts is not None:
                self.gd['ica'][lookup_key]['timecourse'] = ica_ts[:,k]
            else:
                self.gd['ica'][lookup_key]['timecourse'] = None
        else:
            for lookup_key in self.gd['ica'].keys():
                k = re.findall(r'\d+$', lookup_key) #get last digit in IC comp. name
                k = int(k[0]) if len(k) > 0 else None
                if ica_ts is not None and k is not None:
                    self.gd['ica'][lookup_key]['timecourse'] = ica_ts[:,k-1]
                else:
                    self.gd['ica'][lookup_key]['timecourse'] = None

                                
    def browse_icn_files(self, append=True):
        """File browser & loading for ICN templates"""
        
        icn_dir = opj(self.config['base_directory'], self.config['icn']['directory'])
        icn_files = self.browse_files(title='Select ICN Template(s):', directory=icn_dir,
                                      filter="Image Files (*.nii.gz *.nii *.img)")
        if icn_files:
            if len(icn_files) == 1:
                self.config['icn']['directory'] = os.path.dirname(icn_files[0])
            else:
                self.config['icn']['directory'] = os.path.commonpath(icn_files)
            self.add_files_to_list(self.listWidget_ICNtemplates, 'icn', icn_files,
                                   search_pattern=self.config['icn']['search_pattern'],
                                   extra_items=self.config['icn']['extra_items'], append=append)
            
            if len(icn_files) == 1:     #check if .csv table accompanies 4d nifti icn_file w/ ICN names
                if os.path.isfile(os.path.splitext(icn_files[0])[0] + '.csv'):
                    find_csv_labels = False
                    csv_fname = os.path.splitext(icn_files[0])[0] + '.csv'
                    self.load_icn_customNames(csv_fname)
                elif os.path.isfile(os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'):
                    find_csv_labels = False
                    csv_fname = os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'
                    self.load_icn_customNames(fname=csv_fname, icn_files=icn_files)
                else:
                    find_csv_labels = True
            elif len(icn_files) > 1:
                find_csv_labels = True
            else:
                find_csv_labels = False
#             if find_csv_labels:   #optional fn. to user to load names for 4d nifti, stored in csv file
#                 if QtWidgets.QMessageBox.question(None, '', "Are ICN labels/names different from associated file names?",
#                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
#                                                   QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
#                     os.chdir(os.path.dirname(self.config['icn']['directory']))
#                     self.load_icn_customNames(icn_files=icn_files)


    def load_icn_customNames(self, fname=None, icn_files=None):
        """Load file w/ ICN names, if ICN labels are different from filenames"""
        
        icn_dict = None
        fail_flag = True
        if fname:
            if not os.path.isfile(fname):
                fname = None
        else:
            f_caption = "Select saved table with ICN names"
            f_caption = f_caption + "\n(filenames or ROI intensities in 1st column, new names in 2nd):"
            f_dir = '.'
            f_filter = "csv (*.csv);;Text files (*.txt)"
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, f_caption, f_dir, f_filter)
            if not os.path.isfile(fname):
                fname = None
        if fname:
            if fname.endswith('.csv'):
                with open(fname) as f:
                    names_file = list(csv.reader(f))
            elif fname.endswith('.txt'):
                with open(fname) as f:
                    names_file = f.readlines()
                names_file = [x.strip() for x in names_file]
                names_file = [x.split() for x in names_file]
            if (names_file[0][1:3] == ['ICN Label:', 'Noise Classification:']):
                # Check for csv output from prev. run of networkZoo:
                header, content = names_file[0], names_file[1:]
                header[0:3] = ['ICN File', 'ICN Label', 'Noise Classification']
            elif (len(names_file)-1) == (self.listWidget_ICNtemplates.count()-len(self.config['icn']['extra_items'])): 
                #  check if length of csv (minus header) matches number of ICNs templates (w/o nontemplate_ICN entry)
                header, content = names_file[0], names_file[1:]
                if header[0:2] != ['ICN File', 'ICN Label']:
                    header[0:2] = ['ICN File', 'ICN Label']
                if len(header) >= 3: header[2] = 'Noise Classification'
            else: # assumes csv/txt w/o header: 1st col. is filename for ICN, 
                  #                             2nd col. is label/name for ICN,
                  #                             (optional) 3rd is Noise/ICN classification
                content = list(filter(None, names_file)) #remove empty lines
                header = ['ICN File', 'ICN Label']
                if len(content[0]) > len(header):
                    if any([content[0][2].lower() == s.lower() for s in ['ICN', 'noise']]):
                           header.append('Noise Classification')          
            icn_dict = {h: v for h,v in zip(header, zip(*content))}
            if len(icn_dict) == 0:
                fail_flag = True
            elif len(icn_dict) < 3:
                icn_dict['Noise Classification'] = ('ICN',)*len(content)
                fail_flag = False
            else:
                fail_flag = False
    
        if icn_dict:
            fail_flag = self.replace_ic_customNames(ic_dict=icn_dict, ic_file=icn_files, check_loaded_names=True)
        if fail_flag:
            title = "Error loading ICN names"
            message = "One or more old ICN templates/labels not found in current list of ICN template names"
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            self.config['icn']['labels_file'] = fname
            
    def replace_ic_customNames(self, ic_dict=None, ic_file=None, check_loaded_names=False,
                               list_name='icn', listWidget=None):
        """Replace IC template names w/ names from csv table"""
        
        fail_flag = False
        if not listWidget:
            if not list_name:
                fail_flag = True
                ic_dict = None
            elif list_name == 'icn':
                listWidget = self.listWidget_ICNtemplates
            elif list_name == 'ica':
                listWidget = self.listWidget_ICAComponents
            else:
                fail_flag = True
                ic_dict = None
        if ic_file:
            if isinstance(ic_file, (list, tuple)):
                ic_file = ic_file[0]
        if ic_dict:
            ic_dict_keys = tuple([*ic_dict.keys()])
            ic_dict_vals = tuple([*ic_dict.values()])
            if 'ICN File' not in ic_dict.keys():
                ic_dict['ICN File'] = ic_dict_keys
            if 'ICN Label' not in ic_dict.keys():
                ic_dict['ICN Label'] = ic_dict_vals
            if 'Noise Classification' not in ic_dict.keys():
                ic_dict['Noise Classification'] = ('ICN',)*len(ic_dict['ICN File'])
            if check_loaded_names:
                modify_loaded_names = False
                if ic_file:
                    fname = os.path.basename(ic_file)
                    if fname.split('.')[-1] in ['nii.gz']:
                        fname = fname.strip('.nii.gz')
                    elif fname.split('.')[-1] in ['nii', 'img', 'hdr']:
                        fname = fname.strip(fname.split('.')[-1])
                        fname = fname.strip('.')
                    item = listWidget.findItems(fname, Qt.MatchExactly)
                    modify_loaded_names = modify_loaded_names | (item is not None) | (len(item) > 0)
                    for k in ic_dict['ICN File']:
                        old_name = os.path.basename(str(k))
                        item = listWidget.findItems(old_name, Qt.MatchExactly)
                        modify_loaded_names = modify_loaded_names | (item is None) | (len(item) == 0)
                    if modify_loaded_names:
                        roi_dict = self.expand_ROI_atlas_vol(ic_dict, ic_file)

            for i,k in enumerate(ic_dict['ICN File']):
                old_name = os.path.basename(str(k))
                new_name = ic_dict['ICN Label'][i]
                item = listWidget.findItems(old_name, Qt.MatchExactly)
                if (item is None) or (len(item) == 0):
                    fail_flag = True
                elif ic_dict['Noise Classification'][i] == 'ICN':
                    if len(listWidget.findItems(new_name, Qt.MatchExactly)) > 0:
                        #  replace templates w/ duplicate names
                        outdated_item = listWidget.findItems(new_name, Qt.MatchExactly)
                        listWidget.takeItem(listWidget.row(outdated_item[0]))
                    listWidget.takeItem(listWidget.row(item[0]))
                    newItem = QtWidgets.QListWidgetItem(new_name)
                    listWidget.addItem(newItem)
                    newItem.setData(Qt.UserRole, new_name)
                    newItem.setText(new_name)
                    self.gd[list_name][new_name] = self.gd[list_name].pop(old_name)
                    self.gd[list_name][new_name]['name'] = new_name
                    self.gd[list_name][new_name]['widget'] = newItem
                else:  # remove templates marked as noise, to avoid duplication
                    listWidget.takeItem(listWidget.row(item[0]))
                    self.gd['icn'].pop(old_name)
        else:
            fail_flag = True
        return fail_flag
    
    
    def expand_ROI_atlas_vol(self, vol_dict, vol_filename=None, 
                             list_name='icn', listWidget=None):
        """Decompresses/rearranges list item for a single atlas vol., 
        with ROIs indexed as integers, into separate list items"""
        
        if not listWidget:
            if not list_name:
                fail_flag = True
                vol_dict = None
            elif list_name == 'icn':
                listWidget = self.listWidget_ICNtemplates
            elif list_name == 'ica':
                listWidget = self.listWidget_ICAComponents
            else:
                fail_flag = True
                vol_dict = None
        if 'ICN File' not in vol_dict.keys():
            roi_inds_onFile = [*vol_dict.keys()]
        else:
            roi_inds_onFile = list(vol_dict['ICN File'])
        roi_inds_onFile = [str(ind) for ind in roi_inds_onFile]
        if 'ICN File' in roi_inds_onFile: roi_inds_onFile.remove('ICN File')
            
        if 'ICN Label' in vol_dict:
            roi_labels = vol_dict['ICN Label']
        else:
            roi_labels = [*vol_dict.values()]
        roi_labels = [str(label) for label in roi_labels]
        roi_dict = {h:v for h,v in zip(roi_inds_onFile, roi_labels)}
        
        if not vol_filename: # try to determine vol_filename from vol_dict['ICN File'] values
            vol_filename = [x.split(',')[0] for x in roi_inds_onFile]
            vol_filename = vol_filename[0]
        elif not isinstance(vol_filename, str):
            if len(vol_filename) > 1: vol_filename = vol_filename[0]
        vol_filename = os.path.basename(vol_filename)
        search_pattern=self.config[list_name]['search_pattern']
        r = re.compile(search_pattern)
        match = re.search(r, vol_filename)
        outdated_lookup = match.groups()[0]
        
        outdated_item = listWidget.findItems(outdated_lookup, Qt.MatchExactly)
        if outdated_item:
            filepath = self.gd[list_name][outdated_lookup]['filepath']
            outdated_img = self.gd[list_name][outdated_lookup]['img']
            roi_array = outdated_img.get_fdata()
            roi_inds = np.unique(roi_array).tolist()
            if 0 in roi_inds: roi_inds.remove(0)
            listWidget.takeItem(listWidget.row(outdated_item[0]))
            self.gd[list_name].pop(outdated_lookup)
            for ind in roi_inds:                    
                roi_img = image.new_img_like(outdated_img, roi_array==ind, copy_header=True)
                roi_lookup = outdated_lookup + ',' + str(ind)
                if str(ind) in roi_dict.keys():
                    roi_label = roi_dict.pop(str(ind))
                else:
                    roi_label = roi_lookup
                roi_dict.update({roi_lookup: roi_label})
                item = QtWidgets.QListWidgetItem(roi_lookup)
                listWidget.addItem(item)
                item.setData(Qt.UserRole, roi_lookup)
                item.setText(roi_lookup)
                self.gd[list_name][roi_lookup] = {'img': roi_img,
                                                  'filepath': filepath,
                                                  'vol_ind' : ind,
                                                  '4d_nii': False,
                                                  'name': roi_lookup,
                                                  'widget': item}
        return(roi_dict)
        
        

#     def browse_single_file(self, listWidget, list_name):
#         """File browser to locate & load single vol."""
        
#         if os.path.exists(self.config[list_name]['directory']):
#             file_dir = self.config[list_name]['directory']
#         else:
#             file_dir = self.config['base_directory']
#         if list_name == 'ica':
#             f_title1 = 'Select image file containing ICA component:'
#             f_title2 = 'Enter Display Name of IC:'
#             f_filter = "Image Files (*.nii.gz *.nii *.img)"
#         elif list_name == 'icn':
#             f_title1 = 'Select image file containing ICN template:'
#             f_title2 = 'Enter Name of ICN template:'
#             f_filter = "Image Files (*.nii.gz *.nii *.img)"
#         file_name, ok = QtWidgets.QFileDialog.getOpenFileName(self, f_title1, file_dir, f_filter)
#         if file_name:
#             if os.path.exists(file_name):
#                 dims = image.load_img(file_name).shape
#                 vol_dim = len(dims)
#             else:
#                 vol_dim = 0
#             if vol_dim < 3: #if 2D nifti choosen by mistake...
#                 QtWidgets.QMessageBox.warning(self, "Error loading Nifti volumes",
#                                               "2D nifti file or GIFT time series file choosen/entered, please select 3D or 4D nifti files")
#             elif vol_dim == 4: #if 4D nifti volumes...
#                 f_title = '4D-Nifti:'
#                 f_text = 'Select 4th-dim indice:'
#                 k, ok = QtWidgets.QInputDialog.getInt(self, f_title, f_text, 1, 1, dims[3])
#                 k = k - 1
#             else:  #if 3D nifti volumes...
#                 k = 0
            
#             search_pattern=self.config[list_name]['search_pattern']
#             r = re.compile(search_pattern)
#             match = re.search(r, file_name)
#             lookup_key = match.groups()[0]
#             lookup_key = lookup_key + ',%d' %(k+1)
#             lookup_name, ok = QtWidgets.QInputDialog.getText(self, f_title2, '', QtWidgets.QLineEdit.Normal, lookup_key)
#             if lookup_name:
#                 file_IndstoNames = {file_name: {k : lookup_name}}
#             else:
#                 lookup_name = lookup_key
#                 file_IndstoNames = None
#             self.add_files_to_list(listWidget, list_name, [file_name], file_IndstoNames, search_pattern, append=True)
#             if list_name == 'ica':
#                 self.load_ica_timeseries([file_name], k, lookup_key)
            
            
    def browse_files(self, title='Select Files', directory='.', filter=''):
        """File browser to load multiple files"""
        
        selected_files = QtWidgets.QFileDialog.getOpenFileNames(self, title, directory, filter)
        selected_files = selected_files[0] #discards filter info contained in 2nd element of tuple
        selected_files = [str(f) for f in selected_files if isinstance(f, str)]
        selected_files.sort()
        return(selected_files)        
                
    def find_files(self, directory, template, search_pattern, listWidget, list_name, 
                   exclude_pattern=None, extra_items=None, append=False):
        """Load single files & find csv w/ custom names"""
        
        if directory: # if user didn't pick a directory don't continue
            if os.path.isfile(directory):
                all_nifti_files = [directory]
            else:
                ds = nio.DataGrabber(base_directory=directory, template=template, sort_filelist=True)
                all_nifti_files = ds.run().outputs.outfiles
            self.add_files_to_list(listWidget, list_name, all_nifti_files, None, search_pattern, exclude_pattern, extra_items, append=append)
            if list_name == 'icn':      #load ICN labels stored in csv file, if applicable
                if os.path.splitext(all_nifti_files[0])[-1] in ['.img', '.hdr', '.nii']:
                    csv_fname = os.path.splitext(all_nifti_files[0])[0] + '.csv'
                elif os.path.splitext(all_nifti_files[0])[-1] not in ['.nii.gz']:
                    csv_fname = os.path.splitext(all_nifti_files[0])[0]
                    csv_fname = os.path.splitext(csv_fname)[0] + '.csv'
                if os.path.isfile(csv_fname):
                    self.load_icn_customNames(csv_fname)
            return(all_nifti_files)
    
    def rename_list_select(self, list_name='ica', listWidget=None):  #7/16/2020 --kw-- needs testing & debugging
        """Open window to select items from specified list & rename"""
        
        if listWidget is None: return #nothing to do
        
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        if list_name == 'mapped':
            title = 'Select ICA > ICN mappings to rename:'
        elif list_name == 'ica':
            title = 'Select ICA components to rename:'
        elif list_name == 'icn':
            title = 'Select ICN/noise templates to rename:'
        else:
            title = 'Select items to rename:'
        self.selectionWin = select.newSelectWin(list_name, listWidget, title=title)
        
        if self.selectionWin.buttonBox.accepted():
            for item in self.listWidget_mappedICANetworks.selectedItems():
                lookup = str(item.data(Qt.UserRole))
                if list_name == 'mapped':
                    d_title = 'Renaming:  ' + lookup
                    d_label = 'Enter new ICA component name:'
                    d_text = self.gd['mapped'][lookup]['ica_custom_name']
                    ica_new_name, ok1 = QtWidgets.QInputDialog.getText(self, d_title, d_label, d_text)
                    d_label = 'Enter new mapped template name:'
                    d_text = self.gd['mapped'][lookup]['icn_custom_name']
                    icn_new_name, ok2 = QtWidgets.QInputDialog.getText(self, d_title, d_label, d_text)
                    if ok1 or ok2:
                        ica_lookup = self.gd['mapped'][lookup]['ica_lookup']
                        icn_lookup = self.gd['mapped'][lookup]['icn_lookup']
                        self.add_mapped_network(self, ica_icn_pair=(ica_lookup, icn_lookup),
                                                ica_custom_name=ica_new_name,
                                                icn_custom_name=icn_new_name, updateGUI=False)
                        listWidget.takeItem(listWidget.row(item))
                else:
                    if list_name == 'ica':
                        d_title = 'Renaming:  ' + lookup
                        d_label = 'Enter new ICA component name:'
                        d_text = self.gd['ica'][lookup]['name']
                        ica_new_name, ok1 = QtWidgets.QInputDialog.getText(self, d_title, d_label, d_text)
                        if ok1:
                            self.gd['ica'][lookup]['name'] = ica_new_name
                            item.setText(self.gd['ica'][lookup]['name'])
                    elif list_name == 'icn':
                        d_title = 'Renaming:  ' + lookup
                        d_label = 'Enter new mapped template name:'
                        d_text = self.gd['icn'][lookup]['name']
                        icn_new_name, ok2 = QtWidgets.QInputDialog.getText(self, d_title, d_label, d_text)
                        if ok2:
                            self.gd['icn'][lookup]['name'] = icn_new_name
                            item.setText(self.gd['icn'][lookup]['name'])
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)     
        self.update_plots()

    
    def clear_list_select(self, list_name='ica', listWidget=None):  #7/16/2020 --kw-- needs testing & debugging
        """Open window to select items from specified list & remove"""
        
        if listWidget is None: return #nothing to do
        
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        if list_name == 'mapped':
            title = 'Select ICA > ICN mappings to remove:'
        elif list_name == 'ica':
            title = 'Select ICA components to remove:'
        elif list_name == 'icn':
            title = 'Select ICN/noise templates to remove:'
        else:
            title = 'Select items to remove:'
        self.selectionWin = select.newSelectWin(list_name, listWidget, title=title)
        
        if self.selectionWin.buttonBox.accepted():
            if list_name == 'mapped':
                self.delete_mapped_network() #acts on all selected items
            else:
                if list_name == 'ica':
                    keep_lookups = self.gd['mapped_ica'].keys()
                elif list_name == 'icn':
                    keep_lookups = self.gd['mapped_icn'].keys()
                    keep_lookups.append(self.config['icn']['extra_items'])
                    keep_lookups.append(self.config['noise']['extra_items'])
                for item in listWidget.selectedItems():
                    lookup = str(item.data(Qt.UserRole))
                    listWidget.takeItem(listWidget.row(item))  # remove item from qlistwidget
                    if lookup not in keep_lookups:   # remove item from gd[list], if not mapped
                        self.gd[list_name].pop(lookup)
        listWidget.clearSelection()                  # deselects current item(s)
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)     
        self.update_plots()
        
        
        
    def clear_list_all(self, list_name='ica', listWidget=None):
        """Empty specified list"""
        
        title = "Warning"
        if list_name=='mapped':
            message = "Reset all current 'ICA > ICN classifications' (lower list), and return ICA components to original list (upper & left)?"
        elif list_name=='ica':
            message = "Clear list of unclassified ICA networks?"
        elif list_name=='icn':
            message = "Clear list of ICN templates?\n  "
            message = message + "ICN Templates used in ICA > ICN classifications will be temporarily hidden"
        if QtWidgets.QMessageBox.question(None, title, message,
                                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                  QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
            if list_name=='mapped':
                listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
                listWidget.selectAll()
                self.delete_mapped_network() #acts on all selected items
                listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            elif list_name=='ica':
                rm_keys = [ica_lookup for ica_lookup in self.gd['ica'].keys() 
                           if ica_lookup not in self.gd['mapped_ica'].keys()]
                for ica_lookup in rm_keys: del self.gd['ica'][ica_lookup]
                self.lineEdit_ICANetwork.clear()
            elif list_name=='icn':
                rm_keys = [icn_lookup for icn_lookup in self.gd['icn'].keys() 
                           if icn_lookup not in self.gd['mapped_icn'].keys()]
                rm_keys = [icn_lookup for icn_lookup in rm_keys 
                           if icn_lookup not in self.config['icn']['extra_items']]
                rm_keys = [icn_lookup for icn_lookup in rm_keys 
                           if icn_lookup not in self.config['noise']['extra_items']]
                for icn_lookup in rm_keys: del self.gd['icn'][icn_lookup]
                self.lineEdit_mappedICANetwork.clear()
            else:
                self.gd[list_name] = {}
            listWidget.clear()
            self.update_plots()


    def add_files_to_list(self, listWidget, list_name, files_to_add, file_inds=None, 
                          search_pattern='*', exclude_pattern=None, extra_items=None, append=True):
        """Add files to list & format info for parsing w/ networkZoo"""
        if not append:
            listWidget.clear() # In case there are any existing elements in the list
            self.gd[list_name] = {}
        
        files_to_add = [f for f in files_to_add if f is not None]
        if len(files_to_add) > 1:
            files_to_add = list(set(files_to_add))  #remove duplicate entires for ICNs stored as 4D nifti files
            files_to_add.sort()
        if search_pattern is not None:
            r = re.compile(search_pattern)
            files_to_add = [f for f in filter(r.search, files_to_add)]
        if exclude_pattern is not None:
            ex = re.compile(exclude_pattern)
            exclude_files = [f for f in filter(ex.search, files_to_add)]
            filtered_files = [f for f in files_to_add if f not in exclude_files]
        else:
            filtered_files = files_to_add
        for file_name in filtered_files:
            if os.path.exists(file_name):
                vol_dim = len(image.load_img(file_name).shape)
            else:
                vol_dim = 0
            if vol_dim < 3: #if 2D nifti choosen by mistake...
                QtWidgets.QMessageBox.warning(self, "Error loading Nifti volumes", 
                                              "2D nifti file or GIFT time series file choosen/entered, please select 3D or 4D nifti files")
            elif vol_dim == 4: #if 4D nifti volumes...
                if file_inds: #used to name individual vols w/n 4d vol.
                    k_range = file_inds[file_name].keys()
                else:
                    k_dim = image.load_img(file_name).shape[3]
                    k_range = range(k_dim)
                for k in k_range:
                    if file_inds:
                        lookup_key = file_inds[file_name][k]
                    else:
                        if search_pattern is not None:
                            match = re.search(r, file_name)
                            lookup_key = match.groups()[0]
                        else:
                            lookup_key = file_name
                        lookup_key = lookup_key + ',%d' %(k+1)
                    item = QtWidgets.QListWidgetItem(lookup_key)
                    listWidget.addItem(item)
                    item.setData(Qt.UserRole, lookup_key)
                    item.setText(lookup_key)
                    self.gd[list_name][lookup_key] = {'img': image.index_img(file_name, k), 
                                                      'filepath': file_name, 
                                                      'vol_ind' : k, 
                                                      '4d_nii': True,
                                                      'name': lookup_key, 
                                                      'widget': item}
            else:  #if 3D nifti volumes...
                match = re.search(r, file_name)
                lookup_key = match.groups()[0]
                item = QtWidgets.QListWidgetItem(lookup_key)
                listWidget.addItem(item)
                item.setData(Qt.UserRole, lookup_key)
                item.setText(lookup_key)
                self.gd[list_name][lookup_key] = {'img': image.load_img(file_name), 
                                                  'filepath': file_name, 
                                                  'vol_ind' : 0,
                                                  '4d_nii': False,
                                                  'name': lookup_key, 
                                                  'widget': item}
                
                if file_inds: #used to name ROIs indexed by vol. intensities
                    if (len(file_inds[file_name]) > 1) | ([*file_inds[file_name].values()][0] != lookup_key):
                        vol_dict = self.expand_ROI_atlas_vol(file_inds[file_name], file_name,
                                                         listWidget=listWidget, list_name=list_name)
                        self.replace_ic_customNames(vol_dict, file_name, check_loaded_names=False,
                                                    list_name=list_name, listWidget=listWidget)
        if extra_items:
            for extra in extra_items:
                if extra not in self.gd[list_name].keys():
                    item = QtWidgets.QListWidgetItem(extra)
                    listWidget.addItem(item)
                    item.setData(Qt.UserRole, extra)
                    item.setText(lookup_key)
                    self.gd[list_name][extra] = {'img': None, 
                                                 'filepath': None, 
                                                 'vol_ind' : 0,
                                                 '4d_nii': False,
                                                 'name': extra, 
                                                 'widget': item}
       
        
    def update_plots(self):
        """Update plots using global plotting options"""
        ica_lookup, icn_lookup = self.get_current_networks()
        if ica_lookup or icn_lookup:
            options = self.get_plot_options(ica_lookup, icn_lookup, coords_from_sliders=False)
            self.plot_x(self.figure_x, **options)
            self.canvas_x.draw()
            self.plot_t(self.figure_t, **options)
            self.canvas_t.draw() 
            
    def update_plots_from_sliders(self):
        """Updates plots after change in x,y,z slider bars,
        without changing global plotting options"""
        
        ica_lookup, icn_lookup = self.get_current_networks()
        if ica_lookup or icn_lookup:
            options = self.get_plot_options(ica_lookup, icn_lookup, coords_from_sliders=True)
            self.plot_x(self.figure_x, **options)
            self.canvas_x.draw()
            self.plot_t(self.figure_t, **options)
            self.canvas_t.draw() 
            
    def get_current_networks(self):
        """Determine which ICs & ICN templates, or mappings are currently selected"""
        if self.listWidget_mappedICANetworks.currentRow() != -1:
            mapping_lookup = str(self.listWidget_mappedICANetworks.currentItem().data(Qt.UserRole))
            ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
            if self.listWidget_ICNtemplates.currentRow() != -1:
                icn_lookup = str(self.listWidget_ICNtemplates.currentItem().data(Qt.UserRole))
            else:
                icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
        elif self.listWidget_ICAComponents.currentRow() != -1:
            ica_lookup = str(self.listWidget_ICAComponents.currentItem().data(Qt.UserRole))
            if self.listWidget_ICNtemplates.currentRow() != -1:
                icn_lookup = str(self.listWidget_ICNtemplates.currentItem().data(Qt.UserRole))
            else:
                icn_lookup = None
        elif self.listWidget_ICNtemplates.currentRow() != -1:
            ica_lookup = None
            icn_lookup = str(self.listWidget_ICNtemplates.currentItem().data(Qt.UserRole))
        else:  # if both mapped networks & unmapped ICA lists are empty, reset GUI
            ica_lookup = None
            icn_lookup = None
            self.config['computed_analysis'] = False
            self.reset_display()
        return ica_lookup, icn_lookup
            
    def get_plot_options(self, ica_lookup, icn_lookup, coords_from_sliders=False):
        """Get all plot options"""
        
        display, coords = self.apply_slice_views(ica_lookup, icn_lookup, coords_from_sliders)
        options = {'ica_lookup': ica_lookup, 'icn_lookup': icn_lookup, 'display': display, 'coords': coords}
        options.update({'show_icn': mp['global']['show_icn']})
        if icn_lookup in self.gd['icn'].keys():
            if not isinstance(self.gd['icn'][icn_lookup]['img'], (Nifti1Image, Nifti1Pair)):
                options.update({'show_icn': False})
        else:
            options.update({'show_icn': False})
        options.update({'show_time_GIFT': tp['items']['show_time_GIFT']})
        options.update({'show_time_average': tp['items']['show_time_average']})
        options.update({'show_time_group': tp['items']['show_time_group']})
        options.update({'show_time_individual': tp['items']['show_time_individual']})
        options.update({'show_spectrum': tp['items']['show_spectrum']})
        
        return options
            
            
    def apply_slice_views(self, ica_lookup, icn_lookup, coords_from_sliders):
        """Determine what data display to use"""
        
        if coords_from_sliders:
            x, y, z = self.get_and_set_slice_coordinates()
        else: x, y, z = (0, 0, 0)
        if ica_lookup in self.gd['ica'].keys():
            ica_img = self.gd['ica'][ica_lookup]['img']
        else: ica_img = None
        if (icn_lookup in self.gd['icn'].keys()) and self.gd['icn'][icn_lookup]['img']:
            map_img = self.gd['icn'][icn_lookup]['img']
        else: map_img = None
            
        if (map_img is not None) and (ica_img is not None):
            map_img = image.resample_to_img(source_img=map_img, target_img=ica_img)
            map_img = image.math_img('img > img.mean()', img=map_img)
            masked_img = masking.apply_mask(ica_img, map_img)
            masked_img = masking.unmask(masked_img, map_img)
        elif ica_img is not None:
            masked_img = ica_img
        elif map_img is not None:
            masked_img = map_img
        else: masked_img = None
        num_slices = int(self.spinBox_numSlices.text())
        
        coords = (x, y, z)
        if self.buttonGroup_xview.checkedButton() == self.radioButton_ortho:
            self.spinBox_numSlices.setEnabled(False)
            self.pushButton_showOverlap.setEnabled(True)
            self.horizontalSlider_Xslice.setEnabled(True)
            self.horizontalSlider_Yslice.setEnabled(True)
            self.horizontalSlider_Zslice.setEnabled(True)
            display = 'ortho'
            if masked_img and not coords_from_sliders:
                x, y, z = plotting.find_xyz_cut_coords(masked_img, activation_threshold=None)
                self.get_and_set_slice_coordinates(x, y, z)
            coords = (x, y, z)
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_axial:
            self.spinBox_numSlices.setEnabled(True)
            self.pushButton_showOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            display = 'z'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='z', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=None, y=None, z=coords)
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_coronal:
            self.spinBox_numSlices.setEnabled(True)
            self.pushButton_showOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            display = 'y'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='y', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=None, y=coords, z=None)
        else:  # Sagittal
            self.spinBox_numSlices.setEnabled(True)
            self.pushButton_showOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            display = 'x'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='x', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=coords, y=None, z=None)
        return display, coords


    def get_and_set_slice_coordinates(self, x=None, y=None, z=None):
        """Determine slice of vol. to plot"""
        x_update, y_update, z_update = True, True, True
        
        if isinstance(x, (int,float)):
            self.horizontalSlider_Xslice.setValue(x)
            self.label_Xslice.setText("X: %d" % x)
        elif isinstance(x, np.ndarray):
            x.sort()
            self.label_Xslice.setText("X:  " + ", ".join([str(int(d)) for d in x]))
            self.label_Yslice.setText("")
            self.label_Zslice.setText("")
            y_update = False
            z_update = False
        elif x_update:
            x = self.horizontalSlider_Xslice.value()
            self.label_Xslice.setText("X: %d" % x)
        else:
            x = self.horizontalSlider_Xslice.value()
            
        if isinstance(y, (int,float)):
            self.horizontalSlider_Yslice.setValue(y)
            self.label_Yslice.setText("Y: %d" % y)
        elif isinstance(y, np.ndarray):
            y.sort()
            self.label_Xslice.setText("")
            self.label_Yslice.setText("Y:  " + ", ".join([str(int(d)) for d in y]))
            self.label_Zslice.setText("")
            x_update = False
            z_update = False
        elif y_update:
            y = self.horizontalSlider_Yslice.value()
            self.label_Yslice.setText("Y: %d" % y)
        else:
            y = self.horizontalSlider_Yslice.value()
            
        if isinstance(z, (int,float)):
            self.horizontalSlider_Zslice.setValue(z)
            self.label_Zslice.setText("Z: %d" % z)
        elif isinstance(z, np.ndarray):
            z.sort()
            self.label_Xslice.setText("")
            self.label_Yslice.setText("")
            self.label_Zslice.setText("Z:  " + ", ".join([str(int(d)) for d in z]))
            x_update = False
            y_update = False
        elif z_update:
            z = self.horizontalSlider_Zslice.value()
            self.label_Zslice.setText("Z: %d" % z)
        else:
            z = self.horizontalSlider_Zslice.value()
            
        return x, y, z 

    
    def figure_x_onClick(self, event):
        """Click to change MNI coords on spatial map display"""
        
        if self.buttonGroup_xview.checkedButton() == self.radioButton_ortho:
            if event.inaxes is None:
                return
            elif event.inaxes == self.figure_x.axes[1]: #coronal section, based on plotting limits ~ MNI coords
                x = event.xdata
                y = self.horizontalSlider_Yslice.value()
                z = event.ydata
            elif event.inaxes == self.figure_x.axes[2]: #saggital section
                x = self.horizontalSlider_Xslice.value()
                y = event.xdata
                z = event.ydata
            elif event.inaxes == self.figure_x.axes[3]: #axial section
                x = event.xdata
                y = event.ydata
                z = self.horizontalSlider_Zslice.value()
            else:
                return
            print('clicked on MNI coords: (x=%d, y=%d, z=%d)' % (x, y, z))
            self.get_and_set_slice_coordinates(x, y, z)
            self.update_plots_from_sliders()
            
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_axial:
            pass        # add code to return coords for section layouts in future
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_coronal:
            pass
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_sagittal:
            pass
        else:
            return
        

    def plot_x(self, fig, ica_lookup, icn_lookup, display='ortho', coords=(0,0,0), *args, **kwargs):
        """Default spatial map plotting"""
        
        show_crosshairs = kwargs['show_crosshairs'] if 'show_crosshairs' in kwargs else mp['global']['crosshairs']
        show_icn = kwargs['show_icn'] if 'show_icn' in kwargs else mp['global']['show_icn']
        show_mapping_name = kwargs['show_mapping_name'] if 'show_mapping_name' in kwargs else mp['global']['show_mapping_name']
        show_ica_name = kwargs['show_ica_name'] if 'show_ica_name' in kwargs else mp['global']['show_ica_name']
        show_icn_templateName = kwargs['show_icn_templateName'] if 'show_icn_templateName' in kwargs else mp['global']['show_icn_templateName']  
        thresh_ica_vol = kwargs['thresh_ica_vol'] if 'thresh_ica_vol' in kwargs else mp['global']['thresh_ica_vol']
        
        anat_img = self.gd['smri']['img']
        if ica_lookup:
            stat_img = self.gd['ica'][ica_lookup]['img']
        elif icn_lookup:
            stat_img = self.gd['icn'][icn_lookup]['img']
        else: #nothing to plot
            return
        if stat_img is None:
            return

        if thresh_ica_vol:
            if 0 < thresh_ica_vol < 1:
                thresh = max([np.nanmax(stat_img.get_fdata()), 
                              -np.nanmin(stat_img.get_fdata())]) * thresh_ica_vol
            else: thresh = thresh_ica_vol
        if not thresh or not isinstance(thresh, Number):
            thresh = None

        fig.clear()
        ax1 = fig.add_subplot(111) if isinstance(fig, Figure) else fig
        
        d = plotting.plot_stat_map(stat_map_img=stat_img, bg_img=anat_img, 
                                   axes=ax1, cut_coords=coords, 
                                   display_mode=display, threshold=thresh,
                                   draw_cross=show_crosshairs, 
                                   annotate=True, colorbar=True)
        if show_icn and isinstance(self.gd['icn'][icn_lookup]['img'], (Nifti1Image, Nifti1Pair)):
            d.add_contours(self.gd['icn'][icn_lookup]['img'], filled=mp['icn']['filled'], alpha=mp['icn']['alpha'], levels=[mp['icn']['levels']], colors=mp['icn']['colors'])
        ax1.set_axis_off()
        
        if show_mapping_name or show_ica_name or show_icn_templateName:
            if ((ica_lookup in self.gd['mapped_ica'].keys() and 
                 (icn_lookup in self.gd['mapped_ica'][ica_lookup].keys())):
                map_item = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                mapping_lookup = map_item.data(Qt.UserRole)
                icn_custom_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
            else:
                icn_custom_name = icn_lookup
            if isinstance(fig, Figure):
                x_pos, y_pos = (0.07, 0.99)
            else:
                _, y_pos = fig.get_ylim()
                y_pos = y_pos - 0.01
                x_pos, _ = fig.get_xlim()
            if show_mapping_name:
                display_text = icn_custom_name if icn_custom_name is not None else ''
                if show_ica_name:
                    display_text = display_text + '\n   ICA component:   %s' % ica_lookup
                if show_icn_templateName:
                    display_text = display_text + '\n   ICN template:   %s' % icn_lookup
            elif show_ica_name:
                display_text = ica_lookup
                if show_icn_templateName:
                    display_text = display_text + '\n   ICN template:   %s' % icn_lookup
            else:
                display_text = icn_lookup
            fig.text(x_pos,y_pos, display_text, 
                     color='white', size=mp['global']['display_text_size'],
                     horizontalalignment='left', verticalalignment='top')
        if isinstance(fig, Figure):
            fig.tight_layout(pad=0)
            
    def plot_t(self, fig=None, ica_lookup=None, coords=(0,0,0), *args, **kwargs):
        """Default time series plotting"""

        show_time_GIFT = kwargs['show_time_GIFT'] if 'show_time_GIFT' in kwargs else tp['items']['show_time_GIFT']
        show_time_individual = kwargs['show_time_individual'] if 'show_time_individual' in kwargs else tp['items']['show_time_individual']
        show_time_average = kwargs['show_time_average'] if 'show_time_average' in kwargs else tp['items']['show_time_average']
        show_time_group = kwargs['show_time_group'] if 'show_time_group' in kwargs else tp['items']['show_time_group']
        show_spectrum = kwargs['show_spectrum'] if 'show_spectrum' in kwargs else tp['items']['show_spectrum']
        significance_threshold = kwargs['significance_threshold'] if 'significance_threshold' in kwargs else tp['global']['significance_threshold']
        Fs = kwargs['sampling_rate'] if 'sampling_rate' in kwargs else tp['global']['sampling_rate']
        
        # No plots to render conditions
        if not (show_time_GIFT or show_time_individual or show_time_average) and not show_time_group and not show_spectrum:
            if 'ax_handles' not in kwargs: fig.clear() # clear existing time series plots in GUI display
            return
        elif not ica_lookup:
            if 'ax_handles' not in kwargs: fig.clear() # clear existing time series plots in GUI display
            return  
        elif 'timecourse' not in self.gd['ica'][ica_lookup].keys():
            if 'ax_handles' not in kwargs: fig.clear() # clear existing time series plots in GUI display
            return
        elif self.gd['ica'][ica_lookup]['timecourse'] is None:
            if 'ax_handles' not in kwargs: fig.clear() # clear existing time series plots in GUI display
            return
        
        # Determine Axes Layout
        if 'ax_handles' in kwargs:
            ax_handles = kwargs['ax_handles']
            axts = ax_handles['axts'] if 'axts' in ax_handles.keys() else None
            axps = ax_handles['axps'] if 'axps' in ax_handles.keys() else None
            axgr = ax_handles['axgr'] if 'axgr' in ax_handles.keys() else None
        else:
            # set up a 2 rows by 5 columns subplot layout, within overall time series subplot itself
            if isinstance(fig, gridspec.GridSpec):
                gs = gridspec.GridSpecFromSubplotSpec(2, 5, fig)
            else:
                gs = gridspec.GridSpec(2, 5)

            if (show_time_GIFT or show_time_individual or show_time_average) and not show_time_group and show_spectrum:
                # handles for single, group, & powerspectrum subplots respectively
                axts, axps = plt.subplot(gs[:, 3:]), plt.subplot(gs[:, :3])  
            elif not (show_time_GIFT or show_time_individual or show_time_average or show_time_group) and show_spectrum:
                axps = plt.subplot(gs[:, :])  # handle for powerspectrum subplots 
            elif not (show_time_GIFT or show_time_individual or show_time_average) and show_time_group and not show_spectrum:
                axgr = plt.subplot(gs[:, :])  # handle for group timeseries subplots
            elif not (show_time_GIFT or show_time_individual or show_time_average) and show_time_group and show_spectrum:
                axgr, axps = plt.subplot(gs[:, 3:]), plt.subplot(gs[:, :3])  # axgr as above, plus axps for power spectrum subplot
            elif (show_time_GIFT or show_time_individual or show_time_average) and not show_time_group and not show_spectrum:
                axts = plt.subplot(gs[:, :])  # handle for single time series subplot
            elif (show_time_GIFT or show_time_individual or show_time_average) and show_time_group and not show_spectrum:
                # axts for single time series subplot, axgr for group time series subplot
                axts, axgr = plt.subplot(gs[:, 3:]), plt.subplot(gs[:, :3])  
            elif (show_time_GIFT or show_time_individual or show_time_average) and show_time_group and show_spectrum:
                # handles for single, group, & powerspectrum subplots respectively
                axts, axgr, axps = plt.subplot(gs[:, 3:]), plt.subplot(gs[0, :3]), plt.subplot(gs[1, :3])  

        # Process Data & Plot
        if (show_time_individual or show_time_average):
            dat = np.abs(self.gd['ica'][ica_lookup]['img'].get_fdata().astype(np.float)) > significance_threshold
            masked = image.new_img_like(self.gd['smri']['img'], dat.astype(np.int))
        if show_time_GIFT:
            ts = self.gd['ica'][ica_lookup]['timecourse']
            n = len(ts)
            # axts.plot(self.gd['ica'][ica_lookup]['timecourse'])
            axts.plot(np.arange(0,n*Fs,Fs), ts)
            axts.spines['right'].set_visible(False)
            axts.spines['top'].set_visible(False)
            axts.set_title('ICA Time-Series')
            axts.set_xlabel('Time (s)')
            axts.set_ylabel('fMRI signal')
            axts.set_facecolor('White')
        if show_time_individual:
            try:
                seed_masker = input_data.NiftiSpheresMasker(mask_img=masked, seeds=[coords], radius=0, detrend=False,
                                                            standardize=False, t_r=4., memory='nilearn_cache',
                                                            memory_level=1, verbose=0)
                ind_ts = seed_masker.fit_transform(self.gd['fmri']['img'])
            except:
                ind_ts = []
            plt.plot(ind_ts, axes=axts, label='Voxel (%d, %d, %d) Time-Series' % (coords[0], coords[1], coords[2]))
            plt.xlabel('Time (s)')
            plt.ylabel('fMRI signal')
            axts.hold(True)
        if show_time_average:
            brain_masker = input_data.NiftiMasker(mask_img=masked,
                                                  t_r=4.,memory='nilearn_cache', memory_level=1, verbose=0)
            ts = brain_masker.fit_transform(self.gd['fmri']['img'])
            ave_ts = np.mean(ts, axis=1)
            plt.plot(ave_ts, axes=axts, label="Average Signal")
            plt.xlabel('Time (s)')
            plt.ylabel('fMRI signal')
            axts.hold(False)
        if show_spectrum:
            n = len(self.gd['ica'][ica_lookup]['timecourse'])
            ps = np.fft.rfft(self.gd['ica'][ica_lookup]['timecourse'], norm='ortho')
            freq_range = np.fft.rfftfreq(n, Fs)
            axps.plot(freq_range, abs(ps))
            axps.fill_between(freq_range, [0]*len(freq_range), abs(ps))
            axps.spines['right'].set_visible(False)
            axps.spines['top'].set_visible(False)
            axps.set_title('Power Spectrum')
            axps.set_xlabel('Freq. (Hz)')
            axps.set_ylabel('Magnetude')
            axps.set_facecolor('White')
        if isinstance(fig, Figure):
            fig.tight_layout(pad=0)
            


#     def concat_images(self, fig_pieces, fname, cleanup=True, concat_vertical=True, recurse_call=False):
#         """Concatenates saved images into single file, using PyQt5"""
        
#         if os.path.splitext(fname)[-1] != '.png':
#             fname = fname + '.png'
            
#         # Ensure dimensions fit within QPixMap limits
#         pixmaps = []
#         pixmap_widths = []
#         pixmap_heights = []
#         for piece in fig_pieces:
#             pixmap = QPixmap(piece)
#             pixmaps.append(pixmap)
#             pixmap_widths.append(pixmap.size().width()) 
#             pixmap_heights.append(pixmap.size().height())
#         fig_pieces_select = []
#         fig_pieces_leftover = []
#         if concat_vertical and (sum(pixmap_heights) > 2**15): #max. pixels on any dim = 2^15
#             for n in range(len(pixmap_heights)):
#                 if sum(pixmap_heights[0:n+1]) < 2**15:
#                     fig_pieces_select.append(fig_pieces[n])
#                 else:
#                     fig_pieces_leftover.append(fig_pieces[n])
#         elif (sum(pixmap_widths) > 2**15):
#             for n in range(len(pixmap_widths)):
#                 if sum(pixmap_widths[0:n+1]) < 2**15:
#                     fig_pieces_select.append(fig_pieces[n])
#                 else:
#                     fig_pieces_leftover.append(fig_pieces[n])
                    
#         # Assemble & concatenate figs. exceeding pixmap limits
#         if len(fig_pieces_leftover) > 0:
#             fig_pieces = fig_pieces_select
            
#             fname = os.path.splitext(fname)[0]
#             m = re.search(r'\d+$', fname)
#             if m is None: #if fname does not end in a digit...
#                 fname_leftover = fname + '2.png'
#                 fname = fname + '1.png'
#             elif not recurse_call:  #if this is the first call to fn. & fname already ends in a digit...
#                 fname_leftover = fname + '_2.png'
#                 fname = fname + '_1.png'
#             else: #assume this is a recursive call to fn., index digit for recursion already added by prev. fn. call...
#                 fname_leftover = re.sub(r'\d+$', '', fname)
#                 fname_leftover = fname_leftover + str(int(m.group()) + 1) + '.png'
#                 fname = fname + '.png'
                
#             title = "Warning: Concatenating Large Figures"
#             message = "Concatenating all displays will exceed allowed figure dimensions. Saving output as .png files:\n"
#             message = message + "\n   " + os.path.basename(fname) + "\n   " + os.path.basename(fname_leftover)
#             message = message + "\n\nTo create a single figure, suggest removing one or more network classifications, then re-creating output"
#             QtWidgets.QMessageBox.warning(self, title, message)

#             self.concat_images(fig_pieces_leftover, fname_leftover,
#                                cleanup=cleanup, concat_vertical=concat_vertical,
#                                recurse_call=True)

#         # Assemble & concatenate figure pieces
#         pixmaps = []
#         pixmap_widths = []
#         pixmap_heights = []
#         for piece in fig_pieces:
#             pixmap = QPixmap(piece)
#             pixmaps.append(pixmap)
#             pixmap_widths.append(pixmap.size().width()) 
#             pixmap_heights.append(pixmap.size().height())
#         x_start, x_end, y_start, y_end = 0, 0, 0, 0
#         if concat_vertical:
#             pixCanvas = QPixmap(max(pixmap_widths), sum(pixmap_heights))
#             painter = QPainter(pixCanvas)
#             for n,pixmap in enumerate(pixmaps):
#                 painter.drawPixmap(QRectF(x_start,y_start,pixmap_widths[n],pixmap_heights[n]), 
#                                    pixmap, QRectF(pixmap.rect()))
#                 y_start = y_start + pixmap_heights[n]
#         else: # concat images horizontally
#             pixCanvas = QPixmap(sum(pixmap_widths), max(pixmap_heights))
#             painter = QPainter(pixCanvas)
#             for n,pixmap in enumerate(pixmaps):
#                 painter.drawPixmap(QRectF(x_start,y_start,pixmap_widths[n],pixmap_heights[n]), 
#                                    pixmap, QRectF(pixmap.rect()))
#                 x_start = x_start + pixmap_widths[n]
#         success = painter.end()
#         if success:
#             success = pixCanvas.save(fname, "PNG")
#         if success and cleanup:
#             for fig_file in fig_pieces:
#                 if os.path.exists(fig_file):
#                     os.remove(fig_file)
#         return fname

#     def generate_output(self):
#         """Create png w/ all mappings & associated csv file w/ mapping info"""
        
#         btn_txt = self.pushButton_createOutput.text()
#         self.pushButton_createOutput.setText("Creating...")
        
#         output_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Outfiles As:", 
#                                                                self.config['output_directory'])
#         if output_path:
#             if os.path.splitext(output_path)[-1] in ['.img', '.hdr', '.nii', '.csv', '.png', '.jpg', '.jpeg', '.csv', '.gz']:
#                 output_path = os.path.splitext(output_path)[0]
#                 if os.path.splitext(output_path)[-1] in ['.nii', '.tar']:
#                     output_path = os.path.splitext(output_path)[0]
#             out_dir = os.path.dirname(output_path)
#             if not os.path.exists(out_dir):
#                 os.makedirs(out_dir)
#             out_basename = os.path.basename(output_path)
#             concatFig_fname = opj(out_dir, out_basename + '.png') #  single png with all spatial maps
#             csv_fname = opj(out_dir, out_basename + '.csv') # Create name for csv file, based off of root dir. for ICA spatial maps

#             title = 'Generating Summary Output of Analysis'
#             message = 'Creating figures & tables summarizing all current ICA mappings to ICN templates:\n'
#             message = message + '\n  ' + os.path.basename(concatFig_fname) + ': concatenated displays for all ICNs'
#             message = message + '\n  ' + os.path.basename(csv_fname) +       ': table with ICA filenames, ICN labels, etc.'
#             message = message + '\n\nFiles will be created in:\n  ' + out_dir
#             QtWidgets.QMessageBox.information(self, title, message)

#             # Create png figure w/ ortho slices, time series & power spectrum
#             figs_to_gzip = []
#             images_to_concat = []
#             images_to_concat_flagged = []
#             images_ICA_fnames = []
#             images_ICA_fnames_flagged = []
#             images_ICN_names = []
#             images_ICN_names_flagged = []
#             for k, mapping_lookup in enumerate(self.gd['mapped'].keys()):
#                 ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
#                 ica_name = self.gd['mapped'][mapping_lookup]['ica_custom_name']
#                 icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
#                 icn_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
#                 icn_name.strip('...')

#                 self.listWidget_mappedICANetworks.setCurrentItem(self.gd['mapped'][mapping_lookup]['mapped_item'])
#                 self.listWidget_ICNtemplates.setCurrentItem(self.gd['icn'][icn_lookup]['widget'])
#                 self.update_plots()

#                 fname = opj(out_dir, '%s--%s.png' % (ica_name, icn_name))
#                 fname_saved = self.save_display(fname, cleanup=True)
#                 images_to_concat.append(fname_saved)
#                 images_ICA_fnames.append(ica_name)
#                 images_ICN_names.append(icn_name)
#                 if re.match('\\.*noise', icn_lookup, flags=re.IGNORECASE):
#                     images_to_concat_flagged.append(fname_saved)
#                     images_ICA_fnames_flagged.append(ica_name)
#                     images_ICN_names_flagged.append(icn_name)
                
#             # Sort ICs alphabetically by ICA file names & append into noise ICs at end,
#             #  where lambda fn. separates string w/ ',' then casts last part into digit if needed
#             ICAnames_inds_sorted = sorted(range(len(images_ICA_fnames)), 
#                                           key=lambda k: (int(images_ICA_fnames[k].partition(',')[-1]) if images_ICA_fnames[k][-1].isdigit() else float('inf')))
#             images_to_concat = [images_to_concat[k] for k in ICAnames_inds_sorted]
#             images_to_concat = images_to_concat + images_to_concat_flagged
#             for flagged in images_to_concat_flagged: images_to_concat.remove(flagged)
#             images_ICA_fnames = [images_ICA_fnames[k] for k in ICAnames_inds_sorted]
#             images_ICA_fnames = images_ICA_fnames + images_ICA_fnames_flagged
#             for flagged in images_ICA_fnames_flagged: images_ICA_fnames.remove(flagged)
#             images_ICN_names = [images_ICN_names[k] for k in ICAnames_inds_sorted]
#             images_ICN_names = images_ICN_names + images_ICN_names_flagged
#             for flagged in images_ICN_names_flagged: images_ICN_names.remove(flagged)
                
#             # Create single png with all mappings   
#             self.concat_images(images_to_concat, concatFig_fname,
#                                concat_vertical=True, cleanup=True)

#             # Create csv w/ ICA networks & named ICN matches as columns
#             #     NOTE: for completeness, all ICs in ICA list are included in table, even if not mapped or in 4d Nifti
#             icn_info = {}
#             for ica_lookup in self.gd['ica'].keys():
#                 if ica_lookup in self.gd['mapped_ica'].keys():
#                     map_item = self.gd['mapped_ica'][ica_lookup]
#                     mapping_lookup = map_item.data(Qt.UserRole)
#                     icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
#                     icn_custom_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
#                     noise_id = 'noise' if re.match('\\.*noise', icn_lookup, flags=re.IGNORECASE) else 'ICN'
#                     ica_custom_name = self.gd['mapped'][mapping_lookup]['ica_custom_name']

#                     if (icn_lookup in self.config['icn']['extra_items'] 
#                             or icn_lookup in self.config['noise']['extra_items']):
#                         corr_r = float('inf')
#                     elif (hasattr(self, 'mapper') and hasattr(self.mapper, 'corr') 
#                               and (ica_lookup in self.mapper.corr.keys())
#                               and (icn_lookup in self.mapper.corr[ica_lookup].keys())):
#                         corr_r = '%0.2f' % self.mapper.corr[ica_lookup][icn_lookup]
#                     else:
#                         corr_r = float('inf')
#                     icn_info[ica_custom_name] = (icn_custom_name, noise_id, icn_lookup, corr_r)
#                 else:
#                     icn_info[ica_custom_name] = ('?', '?', '?', 0)    
#             with open(csv_fname, 'w') as f:
#                 writer = csv.writer(f)
#                 writer.writerow(('ICA component:', 'ICN Label:', 'Noise Classification:', 'Template match:', 'Corr. w/ template:'))
#                 # lambda fn. below separates string w/ ',' then casts last part into digit if needed
#                 for k in sorted(icn_info.keys(), key=lambda item: (int(item.partition(',')[-1]) if item[-1].isdigit() else float('inf'))):
#                     writer.writerow((k, icn_info[k][0], icn_info[k][1], icn_info[k][2], icn_info[k][3]))

#             self.pushButton_createOutput.setText(btn_txt)
#         else:
#             self.pushButton_createOutput.setText(btn_txt)
    
    
    def create_binaryMasks(self):
        """Create binary masks from mapped ICA components"""
        
        mask_dtype = np.bool_   # data type for saved masks
        thresh_quantile = True  # threshold masks based on sample quantiles?
        thresh_max = True       # threshold mask based on fraction of top value?
        smooth_mask = True      # dilate & smooth mask w/ min. kernel, to fill in holes & improve fit (recommended by nilearn)
        cutoff_quantile = 99.   # if thresh_q, top __% of voxels included in mask
        cutoff_fractMax = 0.33   # if thresh_max, faction of max value used for cutoff
        
        if len(self.gd['mapped']) == 0:
            title = "Error Creating Masks"
            message = "Empty classification list. No ICs have been mapped to ICNs. Cannot currently create Masks"
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            mask_fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Mask As:", self.config['base_directory'])
            if mask_fname:
                if os.path.splitext(mask_fname)[-1] in ['.img', '.hdr', '.nii', '.csv']:
                    mask_fname = os.path.splitext(mask_fname)[0]
                elif os.path.splitext(mask_fname)[-1] in ['.gz']:
                    mask_fname = os.path.splitext(mask_fname)[0]
                    if os.path.splitext(mask_fname)[-1] in ['.nii']:
                        mask_fname = os.path.splitext(mask_fname)[0]
                mask_dir = os.path.dirname(mask_fname)
                mask_basename = os.path.basename(mask_fname)
                mask_fname = opj(mask_dir, mask_basename + '.nii.gz')
                csv_fname = opj(mask_dir, mask_basename + '.csv')
                    
                title = 'Creating Masks from classified ICs'
                message = ''
                if thresh_quantile:
                    message = message + 'Classified ICs will be thresholded using the top '+str(cutoff_quantile)+'% of voxels. '
                if thresh_max:
                    message = message + 'Classified ICs will be thresholded using '+str(cutoff_fractMax)+' * maximum value. '
                message = message + '\n\nCreating files:'
                message = message + '\n  ' + os.path.basename(mask_fname) + ': 4D-nifti containing ICs classified as ICNs'
                message = message + '\n  ' + os.path.basename(csv_fname) + ': ICN names/labels for above nifti'
                message = message + '\n\nFiles will be created in:\n  ' + mask_dir
                QtWidgets.QMessageBox.information(self, title, message)

                # Create 4D nifti binary mask
                mask_noise = []
                mask_imgs = []
                mask_names = []
                
                # lambda fn. below separates string w/ '>' then casts last part into digit if needed
                for mapping_lookup in sorted(self.gd['mapped'].keys(), key=lambda item: (int(item.partition('>')[-1]) if item[-1].isdigit() else float('inf'))):
                    ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
                    icn_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
                    if re.match('\\.*noise', icn_name, flags=re.IGNORECASE):
                        mask_noise.append('noise')
                    else:
                        mask_noise.append('ICN')
                    
                    ica_img = self.gd['ica'][ica_lookup]['img']
                    ica_dat = ica_img.get_fdata()
                    ica_dat[np.isnan(ica_dat)] = 0
                    if thresh_quantile:
                        threshold = np.percentile(ica_dat, cutoff_quantile)
                        ica_dat[ica_dat < threshold] = 0
                    if thresh_max:
                        threshold = ica_dat.max() * cutoff_fractMax
                        ica_dat[ica_dat < threshold] = 0
                    ica_dat[ica_dat > 0] = 1
                    if smooth_mask:
                        ica_dat = binary_dilation(ica_dat) #smooths edges & fills holes in mask
                        ica_dat = binary_dilation(ica_dat) #repeat, further smoothing
                    new_ica_img = image.new_img_like(ica_img, ica_dat, copy_header=True)
                    mask_imgs.append(new_ica_img)
                    mask_names.append(icn_name)
                image.concat_imgs(mask_imgs, dtype=mask_dtype, auto_resample=True).to_filename(mask_fname)
                
                # Create csv w/ ICA networks & named ICN matches as columns
                icn_info = {}
                for k,icn_name in enumerate(mask_names):
                    ic_name = mask_basename + ',%d' %(k+1)
                    icn_info[ic_name] = (icn_name, mask_noise[k])
                with open(csv_fname, 'w') as f:
                    writer = csv.writer(f)
                    writer.writerow(('ICA component:', 'ICN Label:', 'Noise Classification:'))
                    for ic in sorted(icn_info.keys(), key=lambda item: (int(item.partition(',')[-1]) if item[-1].isdigit() else float('inf'))): #lambda separates string w/ ',' then casts last part into digit if needed
                        writer.writerow((ic, icn_info[ic][0], icn_info[ic][1]))
            else:
                QtWidgets.QMessageBox.warning(self, "Error Creating Masks", "Save filename not selected")
            
            

    def quit_gui(self):
        """Fine, acabado, al-nahaya"""
        
        sys.stderr.write('\r')
        if self.config['computed_analysis'] and not self.config['saved_analysis'] and (len(self.gd['mapped']) > 0):
            if QtWidgets.QMessageBox.question(None, '', "Save current analysis before exiting networkZoo?",
                                                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                                  QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                self.save_analysis()
        if QtWidgets.QMessageBox.question(None, '', "Are you sure you want quit networkZoo?",
                                         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            # QtWidgets.QApplication.quit()
            sys.exit()
    
    
def main(argv):
    config_file = None
#    try:
#        opts, args = getopt.getopt(argv, "hi:", ["config_file="])
#    except getopt.GetoptError:
#        print('networkZoo.py -i <config_file> ')
#        sys.exit(2)
#    for opt, arg in opts:
#        if opt == '-h':
#            print('networkZoo.py -i <config_file>')
#            sys.exit()
#        elif opt in ("-i", "--config_file"):
#            config_file = arg

    app = QtWidgets.QApplication(sys.argv)  # A new instance of QApplication
    form = NetworkZooGUI(configuration_file=config_file)
    form.show()  # Show the form
    app.exec()  # and execute the app
#     app.exec_()  # and execute the app


if __name__ == '__main__':  # if we're running file directly and not importing it
    main(sys.argv[1:])  # run the main function
        
        
        
