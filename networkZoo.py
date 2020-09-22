
"""
networkZoo.py
"""

# Python Libraries
from os.path import join as opj  # method to join strings of file paths
import getopt  # used to parse command-line input
import os, sys, re, json, csv
from functools import partial
from string import digits
from numbers import Number

# Qt GUI Libraries
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QThread, QRectF
from PyQt5.QtGui import QColor, QPixmap, QPainter


# Mathematical/Neuroimaging/Plotting Libraries
import numpy as np
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


# Backup configuration settings, if needed
from config_settings_backup import default_configuration as config_backup 

# Internal imports
import zoo_MainWin                # Qt GUI for pyqt5 window setup
import zoo_InputFileHandling as io # fns. to handle importing files
import zoo_SelectionWin   as select  # Qt GUI for selecting items from list
import zoo_Mapper      as map     # Qt GUI + progress bar, for numpy correlations between spatial maps
import zoo_ImageSaver as saver    # Qt GUI + progress bar, for saving display & creating output images
import zoo_Preferences as prefs  # Qt GUI dialog to tweak program settings & save 
import zoo_DisplayOpts as disp   # Qt GUI dialog to tweak display & plot settings
import zoo_OutputOpts as outparams # Qt GUI dialog to tweak mask creation & output settings
import zoo_About as about         # Qt window for about info
import zoo_Tutorial as tutorial   # Qt window for Step-by-step tutorial
import zoo_MaskMaker as masks     # fns. to create binary masks

# Selectively suppress expected irrevelant warnings
import warnings
warnings.filterwarnings('ignore', '.*Casting data from int32 to float32.*') #change of datatypes in nilearn
warnings.filterwarnings('ignore', '.*Casting data from int8 to float32.*')
warnings.filterwarnings('ignore', '.*This figure includes Axes that are not compatible.*') #imprecise tight layout in matplotlib
warnings.filterwarnings('ignore', '.*converting a masked element to nan.*') #NaN possible in masks
warnings.filterwarnings('ignore', '.*invalid value encountered in greater.*') #poor NaN handling in nilearn
warnings.filterwarnings('ignore', '.*No contour levels were found.*')  #binary ROI/ICN masks do not have contour levels when plotted in matplotlib




ANATOMICAL_TO_TIMESERIES_PLOT_RATIO = 5
CONFIGURATION_FILE = 'config_settings/config.json'


class NetworkZooGUI(QtWidgets.QMainWindow, zoo_MainWin.Ui_MainWindow):
    """
    Main NetworkZoo GUI, for classifying ICA comp. spatial maps based on ICN template vols
    """
    def __init__(self, configuration_file=None):
        
        super(self.__class__, self).__init__()  # Runs the initialization of the base classes
        self.setupUi(self)  # created in QT Designer; output w/ pyuic5, see zoo_MainWin.py for class
        
        self.reset_analysis()
        
        # Data containers
        self.gd = {}  # gui data; 
        # ...where gd[class][unique_name][file_path, nilearn image object]
        self.gd = {'ica' : {}, 'icn' : {}, 'mapped' : {},
                   'mapped_ica' : {}, 'mapped_icn' : {}}
        self.corrs = {} # dict of correlations, indexed by ic name
        self.matches = {} # dict of top matches, indexed by ic name
        
        # Configuration file defaults
        cfile = configuration_file if isinstance(configuration_file, str) else CONFIGURATION_FILE
        self.load_configuration(cfile) if os.path.isfile(cfile) else self.load_configuration()
        
        # Setup display based on config settings
        if hasattr(self, 'config'):
            if 'allow_multiclassifications' in self.config['ica'].keys():
                state = self.config['ica']['allow_multiclassifications']
                self.action_AllowICAMulticlassifications.setChecked(state)
                if state:
                    self.action_FindDuplicateICAClassifications.setEnabled(True)
            if 'display' not in self.config.keys():
                self.config.update({'display': {}})
            if 'mri_plots' not in self.config['display'].keys():
                self.config['display'].update({'mri_plots': {}})
            if 'global' not in self.config['display']['mri_plots'].keys():
                self.config['display']['mri_plots'].update({'global': {}})
            if 'display_mode' not in self.config['display']['mri_plots']['global'].keys():
                self.config['display']['mri_plots']['global'].update({'display_mode': ''})
            else:
                displayLayout = self.config['display']['mri_plots']['global']['display_mode']
                if displayLayout == 'ortho':
                    self.pushButton_showMaxOverlap.setEnabled(True)
                    self.radioButton_ortho.setChecked(True)
                    self.radioButton_axial.setChecked(False)
                    self.radioButton_coronal.setChecked(False)
                    self.radioButton_sagittal.setChecked(False)
                elif displayLayout == 'axial':
                    self.pushButton_showMaxOverlap.setEnabled(False)
                    self.radioButton_ortho.setChecked(False)
                    self.radioButton_axial.setChecked(True)
                    self.radioButton_coronal.setChecked(False)
                    self.radioButton_sagittal.setChecked(False)
                elif displayLayout == 'coronal':
                    self.pushButton_showMaxOverlap.setEnabled(False)
                    self.radioButton_ortho.setChecked(False)
                    self.radioButton_axial.setChecked(False)
                    self.radioButton_coronal.setChecked(True)
                    self.radioButton_sagittal.setChecked(False)
                elif displayLayout == 'sagittal':
                    self.pushButton_showMaxOverlap.setEnabled(False)
                    self.radioButton_ortho.setChecked(False)
                    self.radioButton_axial.setChecked(False)
                    self.radioButton_coronal.setChecked(False)
                    self.radioButton_sagittal.setChecked(True)
        
        # Setup Input fns.
        self.io = io.InputHandling(self.gd, self.config, self.corrs,
                                   self.listWidget_ICAComponents,
                                   self.listWidget_ICNtemplates,
                                   self.listWidget_Classifications)
        # Load default files
        self.io.configure_ICs() # loads anatomical MRI, ICN templates, etc.
        
        # Setup corr. fns.
        self.mapper = map.Mapper(in_files=self.get_imgs('ica'), 
                                 in_filenames=self.get_img_names('ica'),
                                 map_files=self.get_imgs('icn'), 
                                 map_filenames=self.get_img_names('icn'), 
                                 corrs=self.corrs)

        # Setup non-Qt display defaults
        if hasattr(self, 'config'):
            if 'display' in self.config.keys():
                if 'mri_plots' in self.config['display'].keys():
                    self.mp = self.config['display']['mri_plots'].copy()
                if 'time_plots' in self.config['display'].keys():
                    self.tp = self.config['display']['time_plots'].copy()
        if type(self.mp['global']['display_text_size']) not in (int, float, 'x-large'): 
            self.mp['global']['display_text_size'] = plt.rcParams['font.size'] * 1.44

        
        # Qt set-up for spatial & time data displays
        anat_sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        anat_sp.setVerticalStretch(ANATOMICAL_TO_TIMESERIES_PLOT_RATIO)
        ts_sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        ts_sp.setVerticalStretch(1)
        
        # figure for spatial data
        self.figure_x = plt.figure()
        self.canvas_x = FigureCanvas(self.figure_x)
        self.verticalLayout_plot.addWidget(self.canvas_x)
        self.canvas_x.setSizePolicy(anat_sp)
        
        # change MNI coordinates on click
        self.canvas_x.mpl_connect('button_release_event', self.figure_x_onClick)

        # figure for time & frequency data
        self.figure_t = plt.figure()
        self.canvas_t = FigureCanvas(self.figure_t)
        self.verticalLayout_plot.addWidget(self.canvas_t)
        self.canvas_t.setSizePolicy(ts_sp)

        # connections for menu items
        self.action_LoadAnalysis.triggered.connect(self.load_analysis)
        self.action_SaveAnalysis.triggered.connect(self.save_analysis)
        self.action_ResetAnalysis.triggered.connect(partial(self.reset_analysis, 
                                                            clear_lists=True, 
                                                            clear_display=True, 
                                                            warn=True))
        self.action_runAnalysis.triggered.connect(self.run_analysis)
        self.action_ResetDisplay.triggered.connect(self.reset_display)
        self.action_SaveDisplay.triggered.connect(partial(saver.ImageSaver.save_display, 
                                                          self.figure_x, 
                                                          figure_t=self.figure_t,
                                                          fname=None, 
                                                          output_dir=self.config['base_directory']))
        self.action_Quit.triggered.connect(self.quit_gui)
        
        self.action_EditPreferrences.triggered.connect(self.edit_preferrences)        
        self.action_EditDisplayOptions.triggered.connect(self.edit_display)
        self.action_EditOutputParams.triggered.connect(self.edit_output_opts)
        
        self.action_LoadICAcomps.triggered.connect(self.io.browse_ica_files)
        self.action_RenameICAlist_select.triggered.connect(partial(self.rename_list_select,
                                                                   list_name='ica',
                                                                   listWidget=self.listWidget_ICAComponents))  
        self.action_ClearICAlist_select.triggered.connect(partial(self.clear_list_select,
                                                                  list_name='ica',
                                                                  listWidget=self.listWidget_ICAComponents))
        self.action_ClearICAlist_all.triggered.connect(partial(self.clear_list_all,
                                                               list_name='ica',
                                                               listWidget=self.listWidget_ICAComponents))
        self.action_LoadICNtemplates.triggered.connect(self.io.browse_icn_files)
        self.action_LoadNoisetemplates.triggered.connect(self.io.load_noise_templates)
        self.action_RenameICNtemplates_select.triggered.connect(partial(self.rename_list_select,
                                                                        list_name='icn',
                                                                        listWidget=self.listWidget_ICNtemplates))
        self.action_ClearICNlist_select.triggered.connect(partial(self.clear_list_select,
                                                                  list_name='icn',
                                                                  listWidget=self.listWidget_ICNtemplates))
        self.action_ClearICNlist_all.triggered.connect(partial(self.clear_list_all,
                                                               list_name='icn',
                                                               listWidget=self.listWidget_ICNtemplates))
        self.action_RenameClassifications_select.triggered.connect(partial(self.rename_list_select,
                                                                        list_name='mapped', 
                                                                        listWidget=self.listWidget_Classifications))
        self.action_AllowICAMulticlassifications.triggered.connect(self.allow_ica_multiClass)
        self.action_FindDuplicateICAClassifications.triggered.connect(partial(self.find_duplicate_mappings,
                                                                              duplicated_name='ica'))
        self.action_FindDuplicateICNClassifications.triggered.connect(partial(self.find_duplicate_mappings,
                                                                              duplicated_name='icn'))
        self.action_FindProbableClassifications.triggered.connect(self.find_probable_classifications)
        self.action_FindQuestionableClassifications.triggered.connect(self.find_questionable_classifications)
        self.action_ClearClassifications_select.triggered.connect(partial(self.clear_list_select,
                                                                         list_name='mapped',
                                                                         listWidget=self.listWidget_Classifications)) 
        self.action_ClearClassifications_all.triggered.connect(partial(self.clear_list_all,
                                                                       list_name='mapped',
                                                                       listWidget=self.listWidget_Classifications))
        self.action_createOutput.triggered.connect(self.create_FiguresAndTables)
        self.action_createBinaryMasks.triggered.connect(self.create_Masks)
        
        self.action_ShowAboutInfo.triggered.connect(self.show_about)
        self.action_ShowStepByStepTutorial.triggered.connect(self.show_tutorial)
        self.action_LoadDemoICAcomps.triggered.connect(self.load_demoICA)
        
        
        # Connections for buttons & lists
        self.buttonGroup_xview.buttonReleased.connect(self.change_display_layout)
        self.pushButton_showMaxOverlap.clicked.connect(self.update_plots)
        self.pushButton_icaload.clicked.connect(self.io.browse_ica_files)
        self.pushButton_icnload.clicked.connect(self.io.browse_icn_files)

        self.listWidget_ICAComponents.itemClicked.connect(self.update_gui_ica)
        self.listWidget_ICNtemplates.itemClicked.connect(self.update_gui_icn)
        self.listWidget_Classifications.itemClicked.connect(self.update_gui_classifications)

        self.pushButton_addClassification.clicked.connect(self.add_Classification)
        self.pushButton_rmClassification.clicked.connect(self.delete_Classification)        
        self.pushButton_runAnalysis.clicked.connect(self.run_analysis)
        self.pushButton_createOutput.clicked.connect(self.create_FiguresAndTables)
        
        self.horizontalSlider_Xslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.horizontalSlider_Yslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.horizontalSlider_Zslice.sliderReleased.connect(self.update_plots_from_sliders)
        self.buttonGroup_xview.buttonReleased.connect(self.update_plots)
        
        self.listWidget_ICAComponents.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_ICAComponents.clearSelection()
        self.listWidget_ICAComponents.setCurrentRow(-1)
        self.listWidget_ICNtemplates.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_ICNtemplates.clearSelection()
        self.listWidget_ICNtemplates.setCurrentRow(-1)
        self.listWidget_Classifications.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.listWidget_Classifications.clearSelection()
        self.listWidget_Classifications.setCurrentRow(-1)
        
        
        # Final startup notices
        warning_flag = False
        if not hasattr(self, 'config'):
            warning_flag = True
        elif 'smri_file' not in self.config.keys():
            warning_flag = True
        elif not os.path.isfile(self.config['smri_file']):
            warning_flag = True
        if warning_flag:
            title = "Anatomical/structural MRI vol."
            message = "Path to anatomical MRI vol. not set."
            message += " Slices will be plotted on a white background,"
            message += " which may obscure the outlines of white ICN templates."
            message += "\n\nTo this change setting, select 'Preferrences' from the 'Edit' menu"
            message += " when the main window is opened, and click on 'Reset All Settings' if needed"
            QtWidgets.QMessageBox.warning(self, title, message)

        
        
    
    ##########################################################################
    #-------------------------------------------------
    ### Functions to set default for configuration ###
    #-------------------------------------------------
    def load_configuration(self, fname=None):
        """Loads configuration settings, either from stored .json file, or re-load from stored config"""

        if 'mypath' not in locals(): mypath = None
        if 'config_backup' not in locals(): config_backup = None
        warning_flag, configData = False, None
        if fname:
            if isinstance(fname, str):
                if os.path.isfile(fname):
                    if os.stat(fname).st_size == 0:
                        title = "Error configuring networkZoo"
                        message = "Configuration file:  " + fname
                        message += "  is an empty file! Defaulting to backup config file..."
                        QtWidgets.QMessageBox.warning(self, title, message)
                        io.InputHandling.replace_faulty_config(fname)
                        
                    with open(fname) as json_config:
                        configData = json.load(json_config)
                elif os.path.isfile(opj(mypath, fname)):
                    fname = opj(mypath, fname)
                    with open(fname) as json_config:
                        configData = json.load(json_config)
                else:
                    warning_flag = True
            elif isinstance(fname, dict):
                if all (key in fname.keys() for key in ['ica', 'icn', 'smri_file']):
                    configData = fname
                else:
                    warning_flag = True
            elif hasattr(self, 'config'):
                configData = self.config
            else:
                warning_flag = True
        else:
            warning_flag = True
            
        if warning_flag:
            if 'configData' not in locals():
                if config_backup:
                    configData = config_backup
                else:
                    configData = io.InputHandling.replace_faulty_config(None)
            if hasattr(self, 'config'):
                title = "Error configuring networkZoo"
                message = "New configuration file not found, defaulting to backup configuration settings"
            else:
                title = "Error starting networkZoo"
                message = "Configuration file not found, defaulting to original, non-modified settings."
            QtWidgets.QMessageBox.warning(self, title, message)
        
        self.config_file = fname if isinstance(fname, str) else None
        if configData:
            self.config = io.InputHandling.config_check_defaults(configData, 
                                                                 mypath=mypath, 
                                                                 config_backup=config_backup)
                                                                      
    #-------------------------------------------
    ### Functions related to overall display ###
    #-------------------------------------------
    def change_display_layout(self):
        """Change layout of slices plotted on display"""
        
        if self.buttonGroup_xview.checkedButton() == self.radioButton_ortho:
            self.mp['global'].update({'display_mode': 'ortho'})
            self.pushButton_showMaxOverlap.setEnabled(True)
            self.horizontalSlider_Xslice.setEnabled(True)
            self.horizontalSlider_Yslice.setEnabled(True)
            self.horizontalSlider_Zslice.setEnabled(True)
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_axial:
            self.mp['global'].update({'display_mode': 'axial'})
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
        elif self.buttonGroup_xview.checkedButton() == self.radioButton_coronal:
            self.mp['global'].update({'display_mode': 'coronal'})
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
        else:  # Sagittal
            self.mp['global'].update({'display_mode': 'sagittal'})
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
        self.update_plots()
                
        
    
    def reset_display(self, initialize=False):
        """Clear Qt display & unselect lists"""
        
        self.figure_x.clear()
        self.canvas_x.draw()
        self.figure_t.clear()
        self.canvas_t.draw()
        
        self.listWidget_ICAComponents.clearSelection()
        self.listWidget_ICAComponents.setCurrentRow(-1)
        self.listWidget_Classifications.clearSelection()
        self.listWidget_Classifications.setCurrentRow(-1)

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
                    self.gd['icn'][icn_lookup]['widget'] = item
                    item.setText(extra)
        self.listWidget_ICNtemplates.clearSelection()
        self.listWidget_ICNtemplates.setCurrentRow(-1)
        
    
    #---------------------------------------------------
    ### Functions triggered by GUI file menu actions ###
    #---------------------------------------------------
    def edit_preferrences(self):
        """Launch window to edit preferrences & save to default file config.json"""
        
        self.editedPreferrences = prefs.EditPreferrencesGUI(self.config,
                                                            config_backup=config_backup,
                                                            config_file=self.config_file)
        if self.editedPreferrences.response ==QtWidgets.QDialog.Accepted:
            self.config = self.editedPreferrences.config
            # Update lists accordingly
            ica_multiClass = self.config['ica']['allow_multiclassifications']
            self.action_AllowICAMulticlassifications.setChecked(ica_multiClass)    
        
    def edit_display(self):
        """Launch window to edit display & plotting preferrences"""
        
        self.editedDisplay = disp.EditDisplayOptions(self.mp, self.tp, 
                                                     self.update_plots,
                                                     current_config=self.config,
                                                     config_file=self.config_file)
        if self.editedDisplay.response ==QtWidgets.QDialog.Accepted:
            self.mp = self.editedDisplay.mp
            self.tp = self.editedDisplay.tp
            self.update_plots()
        else:
            self.mp = self.editedDisplay.mp_prev
            self.tp = self.editedDisplay.tp_prev
            
    def edit_output_opts(self):
        """Launch window to edit output & mask creation options"""
        
        self.editedOutputparams = outparams.EditOutputOptionsGUI(self.config,
                                                                 config_file=self.config_file)
        if self.editedOutputparams.response ==QtWidgets.QDialog.Accepted:
            self.config = self.editedOutputparams.config
                            
        
    def create_FiguresAndTables(self):
        """Create Figures & Tables for all mappings"""
                
        f_caption = "Save Table and Figure(s) As:"
        f_dir = self.config['output_directory']
        if not os.path.isdir(f_dir): f_dir = mypath 
        f_filter = "Image figure (*.png);;Table of classifications (*.csv)"
        output_path, ok = QtWidgets.QFileDialog.getSaveFileName(self, f_caption,
                                                                f_dir, f_filter)
        if ok:
            btn_txt = self.pushButton_runAnalysis.text()
            self.pushButton_runAnalysis.setText("Creating...")
            extra_items = self.config['icn']['extra_items']
            extra_items += self.config['noise']['extra_items']
            
            self.saverGUI = saver.PatienceTestingGUI(self.gd,
                                                     self.config,
                                                     self.listWidget_Classifications,
                                                     self.listWidget_ICNtemplates,
                                                     self.update_plots,
                                                     self.figure_x,
                                                     self.figure_t,
                                                     self.corrs,
                                                     extra_items = extra_items,
                                                     output_path = output_path)
            warnflag = False
            output_files = [os.path.basename(f) for f in self.saverGUI.output.output_files if os.path.exists(f)]
            if output_files:
                self.config['output_created'] = True
                output_png = [f for f in output_files if os.path.splitext(f)[-1] in ['.png']]
                output_csv = [f for f in output_files if os.path.splitext(f)[-1] in ['.csv']]
            else:
                warnflag = True
                
            title = "Finished generating analysis' output summary"
            if warnflag:
                message = 'Output files not created! '
                if self.saverGUI.output.stopImageSaver:
                    image_frag_path = self.saverGUI.output.output_path
                    message += '\n\nImage creator interrupted,'
                    message += ' figure fragments may remain in: ' + image_frag_path + '.\n\n'
                message += 'See python log or terminal output for error messages'
                QtWidgets.QMessageBox.warning(self, title, message)
            else:
                message = 'Created figures & tables, summarizing all current ICA classifications'
                if output_png:
                    message += '\n\nConcatenated displays for all ICNs:'
                    for file in output_png:
                        message += '\n  ' + file
                if output_csv:
                    message += '\n\nTable with ICA filenames, ICN labels, etc.:'                    
                    for file in output_csv:
                        message += '\n  ' + file
                message += '\n\nAll files saved in:\n  ' + self.saverGUI.output.outputDir
                QtWidgets.QMessageBox.information(self, title, message)
            
            self.pushButton_runAnalysis.setText(btn_txt)
            
            
    def create_Masks(self):
        """Create masks from mapped ICA components,
        labelled by associated ICN templates"""
        
        if len(self.gd['mapped']) == 0:
            title = "Error Creating Masks"
            message = "Empty classification list. No ICs have been mapped to ICNs."
            message += " Cannot currently create Masks"
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            mask_fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, 
                                                                  "Save Mask As:", 
                                                                  self.config['base_directory'])
            if not mask_fname:
                QtWidgets.QMessageBox.warning(self, "Error Creating Masks", "Save filename not selected")
            else:
                self.masks = masks.MaskMaker(self.gd, config=self.config)
                self.masks.create_binaryMasks(mask_fname)
                
                
    def show_about(self):
        """Pull up window to background details & aims of software"""
        about_file = opj(self.config['base_directory'], 'ABOUT.txt')
        self.about = about.newAboutWin(file=about_file)
        
        
    def show_tutorial(self):
        """Step-by-step tutorial, to find current step in analysis & giving tips for next step(s)"""
        
        loadedICA = True if (self.listWidget_ICAComponents.count() > 0) else False
        loadedICNs = True if (self.listWidget_ICNtemplates.count() > 0) else False
        setMappings = True if (self.listWidget_Classifications.count() > 0) else False
        figsCreated = self.config['output_created']
        tutorial.newTutorialWin(loadedICA=loadedICA, loadedICNs=loadedICNs, 
                                setMappings=setMappings, figsCreated=figsCreated)
        
    def load_demoICA(self, demo_ica_path=None):
        """Loads example ICA spatial maps, as demo dataset"""
        
        default_demo = opj('data_templates', 'example_ica_analysis', 'smith2009_ICNs', 'ica20.nii.gz')
        if not demo_ica_path:
            demo_ica_path = default_demo
        elif not os.path.exists(demo_ica_path):
            demo_ica_path = default_demo
        
        if not os.path.exists(demo_ica_path):
            title = "Error Loading Example ICA spatial maps"
            message = "Could not find example ICA dataset:  "
            message += demo_ica_path
            QtWidgets.QMessageBox.warning(self, title, message)
        else:
            title = "Loading Example ICA Spatial Maps"
            message = "   Loading example of ICA output spatial maps,"
            message += " in order to demonstrate basic functionality of Network Zoo..."
            if demo_ica_path==opj('data_example', 'smith2009_ICNs', 'ica20.nii'):
                message += "\n    (Time series may not be included in demo dataset)"
            QtWidgets.QMessageBox.information(self, title, message)
            
            self.io.load_demo_files(demo_ica_path)
                
            
    #--------------------------------------------
    ### Functions controlling entire analysis ###
    #--------------------------------------------
    def reset_analysis(self, clear_lists=False, clear_display=False, warn=False):
        """Reset entire analysis"""
        
        if warn:
            warn_title = "Resetting Analysis"
            message = "All currently loaded ICA files, ICN templates, and classifications will be discarded,"
            message += "\n\nContinue?"
            if QtWidgets.QMessageBox.warning(self, warn_title, message,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No:
                return # do nothing
        if clear_lists:
            self.listWidget_Classifications.clear()
            self.listWidget_ICAComponents.clear()
            self.listWidget_ICNtemplates.clear()
            self.lineEdit_ICANetwork.clear()
            self.lineEdit_mappedICANetwork.clear()
        if not hasattr(self, 'gd'):
            self.gd = {'smri': {}, 'ica': {}, 'icn': {}, 
                       'mapped': {}, 'mapped_ica': {}, 'mapped_icn': {}}
        else:
            self.gd['ica'] = {}
            self.gd['icn'] = {}
            self.gd['mapped'] = {}
            self.gd['mapped_ica'] = {}
            self.gd['mapped_icn'] = {}
        self.corrs = {}
        self.matches = {}
        if clear_display:
            self.reset_display()
        if hasattr(self, 'config'):
            if 'saved_analysis' in self.config.keys():
                self.config['saved_analysis'] = False
            if 'output_created' in self.config.keys():
                self.config['output_created'] = False
            
                
    def save_analysis(self):
        """Save info needed for 'load_analysis()' fn."""
        
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Analysis As:", 
                                                         self.config['base_directory'],
                                                         filter='Saved JSON files (*.json)')
        if fname is None or fname is '':
            QtWidgets.QMessageBox.warning(self, "Error saving analysis", 
                                          "Save filename not selected, analysis not saved")
        else:
            if os.path.splitext(fname)[-1] != '.json': fname = fname + '.json'
            if os.path.exists(fname): os.remove(fname)
            
            if not self.config["saved_analysis"]: 
                title = "Saving analysis"
                message = "Saving to:"
                message += "\n  " + fname
                message += "\n\nOnly paths to ICA volumes & ICN templates will be saved."
                message += " If these files are modified or deleted,"
                message += " saved analysis will not load correctly"
                QtWidgets.QMessageBox.information(self, title, message)
            self.config['saved_analysis'] = True
            self.io.save_analysis_json(fname)

    def load_analysis(self):
        """Load info from file created by 'save_analysis()' fn."""
        
        fname, ok = QtWidgets.QFileDialog.getOpenFileName(self, "Select Saved Analysis file:", 
                                                      '.', 'Saved JSON files (*.json)')
        load_analysis_error = False
        if fname is None or not ok:
            load_analysis_error = True
            title = "Error loading analysis"
            message = "No saved file selected, returning to current analysis"
        else:
            self.reset_analysis(clear_lists=True, clear_display=True, warn=False)
            self.io.load_analysis_json(fname)
            self.load_configuration(self.io.config)
            self.corrs = self.io.corrs

            if self.listWidget_Classifications.count() > 0:
                self.listWidget_Classifications.setCurrentRow(0)
                self.update_gui_classifications(self.listWidget_Classifications.currentItem())
            else:
                self.update_plots()
                
    
    def run_analysis(self):
        """Run full or ongoing correlation analysis for all loaded ICs & ICNs"""
        
        btn_txt = self.pushButton_runAnalysis.text()
        self.pushButton_runAnalysis.setText("Correlating...")
        
        if len(self.gd['ica']) == 0: self.io.browse_ica_files()
        if len(self.gd['icn']) == 0: self.io.browse_icn_files()
        if len(self.gd['ica']) == 0 or len(self.gd['icn']) == 0:
            title = "Error Running Analysis"
            message = "Cannot start correlation analysis."
            if len(self.gd['ica']) == 0:
                message += " No ICA spatial maps loaded."
            if len(self.gd['icn']) == 0:
                message += " No ICN templates loaded."
            QtWidgets.QMessageBox.warning(self, title, message)
            self.pushButton_runAnalysis.setText(btn_txt)
            return
        
        ### Call GUI for progress bar ###
        if not hasattr(self, 'mapper'):
            self.mapper = map.Mapper(in_files=self.get_imgs('ica'), 
                                     in_filenames=self.get_img_names('ica'),
                                     map_files=self.get_imgs('icn'), 
                                     map_filenames=self.get_img_names('icn'), 
                                     corrs=self.corrs)
        self.prbrGUI = map.PatienceTestingGUI(map_files=self.get_imgs('icn'), 
                                              map_filenames=self.get_img_names('icn'), 
                                              in_files=self.get_imgs('ica'), 
                                              in_filenames=self.get_img_names('ica'),
                                              corrs=self.corrs, mapper=self.mapper)
        # Update existing Correlations
        self.pushButton_runAnalysis.setText("Updating...")
        for ica_lookup in self.prbrGUI.mapper.corrs.keys():
            if ica_lookup not in self.corrs.keys():
                self.corrs.update({ica_lookup: {}})
            self.corrs[ica_lookup].update(self.prbrGUI.mapper.corrs[ica_lookup])
                
        # Update GUI
        self.pushButton_runAnalysis.setText(btn_txt)
        if self.listWidget_Classifications.currentRow() != -1:
            mapping_item = self.listWidget_Classifications.currentItem()
            self.update_gui_classifications(mapping_item)
        elif self.listWidget_ICAComponents.currentRow() != -1:
            ica_item = self.listWidget_ICAComponents.currentItem()
            self.update_gui_ica(ica_item)
        elif self.listWidget_ICNtemplates.currentRow() != -1:
            icn_item = self.listWidget_ICNtemplates.currentItem()
            self.update_gui_icn(icn_item)
            
        
    def allow_ica_multiClass(self, state):
        """Allow non-unique classification of ICA comps.,
        where one IC can be mapped to multiple ICNs"""
        
        self.config['ica']['allow_multiclassifications'] = state
        if state:
            title = "Allowing ICA multiclassifications:"
            message = "Multiclassifications now enabled."
            message += " ICA comps. will remain in ICA list following classification,"
            message += " allowing additional classifications with other templates"
            QtWidgets.QMessageBox.information(self, title, message)

            self.action_FindDuplicateICAClassifications.setEnabled(True)
            
            # Ensure all mapped ICA comps. included in ica list
            for ica_lookup in self.gd['mapped_ica'].keys():
                ica_display_name = self.gd['ica'][ica_lookup]['display_name']
                match_count = len(self.listWidget_ICAComponents.findItems(ica_display_name, 
                                                                          Qt.MatchExactly))
                if match_count == 0:
                    item = QtWidgets.QListWidgetItem(ica_lookup)
                    self.listWidget_ICAComponents.addItem(item)
                    item.setData(Qt.UserRole, ica_lookup)
                    item.setText(ica_display_name)
                    self.gd['ica'][ica_lookup]['widget'] = item
        else:
            # Remove mapped ICA comps. from ica list
            for ica_lookup in self.gd['mapped_ica'].keys():
                ica_display_name = self.gd['ica'][ica_lookup]['display_name']
                mapped_ica_items = self.listWidget_ICAComponents.findItems(ica_display_name, 
                                                                           Qt.MatchExactly)
                for item in mapped_ica_items:
                    self.listWidget_ICAComponents.takeItem(self.listWidget_ICAComponents.row(item))
                    
                    
    def quit_gui(self):
        """Fine, acabado, al-nahaya, NetworkZoo is pining for the fjords"""
        
        sys.stderr.write('\r')
        if self.config['saved_analysis'] and not self.config['saved_analysis'] and (len(self.gd['mapped']) > 0):
            if QtWidgets.QMessageBox.question(None, '', "Save current analysis before exiting networkZoo?",
                                                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                                  QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                self.save_analysis()
        if QtWidgets.QMessageBox.question(None, '', "Are you sure you want quit networkZoo?",
                                         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            # QtWidgets.QApplication.quit()
            if 'd_opened' in locals(): # manually close all open nilearn plots, prevent accumulation in memory
                for d in d_opened:
                    d.close()  
                    d_opened.remove(d)
            sys.exit()
            
            
    #-----------------------------------------
    ### Functions to edit Qt lists & items ###
    #-----------------------------------------
    def rename_list_select(self, list_name='ica', listWidget=None):
        """Open window to select items from specified list & rename"""
        
        if listWidget is None: return #nothing to do
        
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        if list_name == 'mapped':
            title0 = 'Select ICA > ICN mappings to rename:'
            label1 = 'Enter new ICA component name:'
            label2 = 'Enter new mapped ICN template name:'
        elif list_name == 'ica':
            title0 = 'Select ICA components to rename:'
            label1 = 'Enter new ICA component name:'
        elif list_name == 'icn':
            title0 = 'Select ICN/noise templates to rename:'
            label1 = 'Enter new ICN template name:'
        else:
            title0 = 'Select items to rename:'
            label1 = 'Enter new name:'
            
        self.selectionWin = select.newSelectWin(listWidget, 
                                                title=title0)
        update_display = False
        if self.selectionWin.accept_result == QtWidgets.QDialog.Accepted:
            for lookup in self.selectionWin.selected_lookup_names:
                title1 = 'Renaming:  ' + lookup
                if list_name == 'mapped':
                    old_name1 = self.gd['mapped'][lookup]['ica_custom_name']
                    old_name2 = self.gd['mapped'][lookup]['icn_custom_name']
                    ica_new_name, ok1 = QtWidgets.QInputDialog.getText(self, title1, 
                                                                       label1, text=old_name1)
                    icn_new_name, ok2 = QtWidgets.QInputDialog.getText(self, title1, 
                                                                       label2, text=old_name2)
                    if ok1 or ok2:
                        if not ok1: ica_new_name = old_name1
                        if not ok2: icn_new_name = old_name2
                        ica_lookup = self.gd['mapped'][lookup]['ica_lookup']
                        icn_lookup = self.gd['mapped'][lookup]['icn_lookup']

                        self.add_Classification(ica_icn_pair=(ica_lookup, icn_lookup),
                                                ica_custom_name=ica_new_name,
                                                icn_custom_name=icn_new_name, updateGUI=False)
                        update_display = True
                else:
                    old_name = self.gd[list_name][lookup]['display_name']
                    title1 = 'Renaming:  ' + old_name
                    new_name, ok = QtWidgets.QInputDialog.getText(self, title1, 
                                                                  label1, text=old_name)
                    if ok:
                        old_name = self.selectionWin.selected_display_names[lookup]
                        old_items = listWidget.findItems(old_name, Qt.MatchExactly)
                        for old_item in old_items:
                            old_item.setText(new_name)
                            self.gd[list_name][lookup]['display_name'] = new_name
                            update_display = True

        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        if update_display:  self.update_plots()

    
    def clear_list_select(self, list_name='ica', listWidget=None, list_subset=None):
        """Open window to select items from specified list & remove"""
        
        if listWidget is None: return #nothing to do
        
        listWidget.clearSelection() #clear all currently selected items
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        extras = []
        if list_name == 'mapped':
            title0 = 'Select ICA > ICN mappings to remove:'
            title1 = 'Removing selected ICA > ICN mappings:'
            message1 = "Reset selected 'ICA > ICN classifications'"
            if not self.config['ica']['allow_multiclassifications']:
                message1 += " and return ICA components to original list (upperleft)?"
            else: message1 += "?"
        elif list_name == 'ica':
            title0 = 'Select ICA components to remove:'
            title1 = 'Removing selected ICA components:'
            message1 = "Clear list of selected ICA components?"
        elif list_name == 'icn':
            title0 = 'Select ICN/noise templates to remove:'
            title1 = 'Removing selected ICN/noise templates:'
            message1 = "Clear list of selected ICN templates?\n  "
            message1 += "(ICN templates used in ICA > ICN classifications,"
            message1 += " as well as blank templates (ex: '...notemplate_ICN'),"
            message1 += " will be temporarily hidden)"
            extra_items = self.config['icn']['extra_items'] + self.config['noise']['extra_items']
            for extra in extra_items:
                item = listWidget.findItems(extra, Qt.MatchExactly)
                if len(item) > 0: # since extra defaults may have been re-named
                    extras.append(item)
        else:
            title0 = 'Select items to remove:'
            title1 = 'Removing selected items:'
            message1 = 'Remove selected item?'

        self.selectionWin = select.newSelectWin(listWidget, title=title0, 
                                                extras=extras, list_subset=list_subset)
        
        update_display = False
        if self.selectionWin.accept_result == QtWidgets.QDialog.Accepted:
            for lookup in self.selectionWin.selected_lookup_names:
                if list_name == 'mapped':
                    old_item = listWidget.findItems(lookup, Qt.MatchExactly)[0]
                    old_item.setSelected(True)
                else:
                    old_name = self.gd[list_name][lookup]['display_name']
                    old_item = listWidget.findItems(old_name, Qt.MatchExactly)[0]
                    old_item.setSelected(True)
                    
            if QtWidgets.QMessageBox.warning(None, title1, message1,
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                             QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                if list_name == 'mapped':
                    self.delete_Classification() #acts on all selected items
                else:
                    if list_name == 'ica':
                        keep_lookups = list(self.gd['mapped_ica'].keys())
                    elif list_name == 'icn':
                        keep_lookups = list(self.gd['mapped_icn'].keys())
                        keep_lookups += extra_items
                    for item in listWidget.selectedItems():
                        lookup = str(item.data(Qt.UserRole))
                        listWidget.takeItem(listWidget.row(item))  # remove item from qlistwidget
                        if lookup not in keep_lookups:   # remove item from gd[list], if not mapped
                            self.gd[list_name].pop(lookup)
                    update_display = True
        listWidget.clearSelection()                  # deselects current item(s)
        listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)   
        if update_display:  self.update_plots()                            
        
        
        
    def clear_list_all(self, list_name='ica', listWidget=None):
        """Empty specified list"""
        
        if list_name=='mapped':
            title = 'Removing all current ICA > ICN mappings:'
            message = "Reset all current 'ICA > ICN classifications' (lower list),"
            message += " and return ICA components to original list (upper & left)?"
        elif list_name=='ica':
            title = 'Removing all unclassified ICA components:'
            message = "Clear list of currently unclassified ICA components?"
        elif list_name=='icn':
            title = 'Removing all ICN/noise templates:'
            message = "Clear list of all ICN & noise templates?\n     "
            message += "      (this will temporarily hide blank templates"
            message += " (ex: '...notemplate_ICN'), "
            message += "as well as all ICN Templatesused in ICA > ICN classifications)"
        else:
            title = 'Removing all items:'
            message = 'Clear list of all items?'
        if QtWidgets.QMessageBox.warning(None, title, message,
                                         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                         QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            if list_name=='mapped':
                listWidget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
                listWidget.selectAll()
                self.delete_Classification() #acts on all selected items
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
        

    #------------------------------------------------------
    ### Functions to get items from GUI data containers ###
    #------------------------------------------------------
    def get_imgs(self, list_name):
        """Select MRI/fMRI image vols. from list"""
        imgs = [img for img in self.get_item_prop(list_name, 'img') if isinstance(img, 
                                                                                (Nifti1Image, Nifti1Pair))]
        return imgs
    
    def get_img_names(self, list_name):
        """Get names for MRI/fMRI vols. in list"""
        imgs = [True if isinstance(img, (Nifti1Image, Nifti1Pair))
                else False for img in self.get_item_prop(list_name, 'img')]
        names_all = [name for name in self.get_item_prop(list_name, 'lookup_name')]
        names = []
        for i, name in enumerate(names_all):
            if imgs[i]:
                names.append(name)
        return(names)
    
    def get_item_prop(self, list_name, list_property):
        """Get item's properties from networkZoo list"""
        return [item[list_property] for item in self.gd[list_name].values()]
 

    #-------------------------------------------------------------------
    ### Functions to handle GUI behavior when a list item is clicked ###
    #-------------------------------------------------------------------
    def update_gui_ica(self, ica_item):
        """Update plotting & selection when clicking on ICA list"""
        
        # Get current IC & ICN names
        ica_lookup = str(ica_item.data(Qt.UserRole))
        mapping_lookup = None
        mapping_icn_lookup = None
        icn_lookup = None
        if self.listWidget_Classifications.currentRow() != -1:
            current_mapping_lookup = str(self.listWidget_Classifications.currentItem().data(Qt.UserRole))
            if ica_lookup == self.gd['mapped'][current_mapping_lookup]['ica_lookup']:
                mapping_lookup = current_mapping_lookup
                mapping_icn_lookup = self.gd['mapped'][current_mapping_lookup]['icn_lookup']
        if self.listWidget_ICNtemplates.currentRow() != -1:
            icn_lookup = str(self.listWidget_ICNtemplates.currentItem().data(Qt.UserRole))
        if (icn_lookup is not None) and (icn_lookup != mapping_icn_lookup):
            mapping_lookup = None #if selected icn & mapped icn disagree, ignore mapping icn
        
        # Check if IC & ICN are a paired mapping
        map_itemWidget = None
        if (icn_lookup is not None) and (mapping_lookup is None):
            if ica_lookup in self.gd['mapped_ica'].keys():
                if icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                    map_itemWidget = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                    mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
        
        # Add IC/ICN pair to corr., if needed
        new_pair = False
        if ica_lookup not in self.corrs.keys():
            new_pair = True
        elif icn_lookup not in self.corrs[ica_lookup].keys():
            new_pair = True
        if new_pair:
            self.correlate_pair(ica_lookup, icn_lookup)
        
        # Clear ICN list & re-rank by corr.
        self.repopulate_ICNs(ica_lookup)
        if icn_lookup in self.gd['icn'].keys():
            icn_item = self.gd['icn'][icn_lookup]['widget']
            self.listWidget_ICNtemplates.setCurrentItem(icn_item)
        
        # Clear other lists & set default placement(s)
        if icn_lookup is None: #if no ICN is currently selected...
            self.listWidget_ICNtemplates.setCurrentRow(-1)
        elif icn_lookup in self.gd['icn'].keys():
            self.lineEdit_mappedICANetwork.setText(self.gd['icn'][icn_lookup]['display_name'])
        if mapping_lookup is None:
            self.listWidget_Classifications.setCurrentRow(-1)
        elif map_itemWidget is not None:
            self.listWidget_Classifications.setCurrentItem(map_itemWidget)
            
        # Update GUI
        self.lineEdit_ICANetwork.setText(self.gd['ica'][ica_lookup]['display_name'])
        self.update_plots()
        
                
    def update_gui_icn(self, icn_item):
        """Update plotting & selection when clicking on ICN list"""
        
        # Get current IC & ICN names
        icn_lookup = str(icn_item.data(Qt.UserRole))
        mapping_ica_lookup = None
        current_ica_lookup = None
        mapping_lookup = None
        if self.listWidget_Classifications.currentRow() != -1: 
            # assume user is exploring alternate ICN classifications, prioritize over selected ica
            mapping_lookup = str(self.listWidget_Classifications.currentItem().data(Qt.UserRole))
            mapping_ica_lookup = str(self.gd['mapped'][mapping_lookup]['ica_lookup'])
        elif self.listWidget_ICAComponents.currentRow() != -1:
            current_ica_lookup = str(self.listWidget_ICAComponents.currentItem().data(Qt.UserRole))
        if (current_ica_lookup is not None) and (current_ica_lookup != mapping_ica_lookup):
            mapping_lookup = None #if selected ica & mapped ica disagree, ignore mapping ica
            ica_lookup = current_ica_lookup
        else:
            ica_lookup = mapping_ica_lookup
            
        # Check if IC & ICN are a paired mapping, or if current mapping does not include IC
        map_itemWidget = None
        if (ica_lookup is not None) and (mapping_lookup is None):
            if icn_lookup in self.gd['mapped_icn'].keys():
                if ica_lookup in self.gd['mapped_icn'][icn_lookup].keys():
                    map_itemWidget = self.gd['mapped_icn'][icn_lookup][ica_lookup]
                    mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
        elif  mapping_lookup and self.config['ica']['allow_multiclassifications']:
            # ignore below if ICA muliclass. not enabled, since mapping_lookup needed to find ICA lookup
            if icn_lookup not in self.gd['mapped_icn'].keys():
                mapping_lookup = None # icn not classified, unselect mapping
            elif ica_lookup not in self.gd['mapped_icn'][icn_lookup].keys():
                mapping_lookup = None  # mapping refers to another ica item, unselect mapping
        
        # Add IC/ICN pair to corr., if needed
        new_pair = False
        if ica_lookup is None:
            new_pair = False
        elif ica_lookup not in self.corrs.keys():
            new_pair = True
        elif icn_lookup not in self.corrs[ica_lookup].keys():
            new_pair = True
        if new_pair:
            self.correlate_pair(ica_lookup, icn_lookup)
            self.repopulate_ICNs(ica_lookup)  # only re-populate list for new pair & new corr.
            if icn_lookup in self.gd['icn'].keys():
                icn_item = self.gd['icn'][icn_lookup]['widget']
                self.listWidget_ICNtemplates.setCurrentItem(icn_item)
        
        # Clear other lists & set default placement(s)
        if ica_lookup is None: #if no ICA is currently selected...
            self.listWidget_ICAComponents.setCurrentRow(-1)
        elif ica_lookup in self.gd['ica'].keys():
            ica_itemWidget = self.gd['ica'][ica_lookup]['widget']
            self.listWidget_ICAComponents.setCurrentItem(ica_itemWidget)
            self.lineEdit_ICANetwork.setText(self.gd['ica'][ica_lookup]['display_name'])
        if mapping_lookup is None:
            self.listWidget_Classifications.setCurrentRow(-1)
        elif map_itemWidget is not None:
            self.listWidget_Classifications.setCurrentItem(map_itemWidget)
        
        # Update GUI
        self.lineEdit_mappedICANetwork.setText(self.gd['icn'][icn_lookup]['display_name'])
        self.update_plots()


    def update_gui_classifications(self, mapping_item):
        """Update plotting & selection when clicking on mapped ICA > ICN list"""
                
        # Get current IC & ICN names
        mapping_lookup = str(mapping_item.data(Qt.UserRole))
        mapping_ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
        mapping_icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
        if self.listWidget_ICAComponents.currentRow() != -1:
            current_ica_lookup = str(self.listWidget_ICAComponents.currentItem().data(Qt.UserRole))
        else:
            current_ica_lookup = None
        if current_ica_lookup and (current_ica_lookup != mapping_ica_lookup):
            current_ica_lookup = None #if selected ica & mapped ica disagree, prioritize mapping
        
        # Add IC/ICN pair to corr., if needed
        new_pair = False
        if mapping_ica_lookup not in self.corrs.keys():
            new_pair = True
        elif mapping_icn_lookup not in self.corrs[mapping_ica_lookup].keys():
            new_pair = True
        if new_pair:
            self.correlate_pair(mapping_ica_lookup, mapping_icn_lookup)
            
        # Clear ICN list & re-rank by corr. order
        self.repopulate_ICNs(mapping_ica_lookup)
        if mapping_icn_lookup in self.gd['icn'].keys():
            current_icn_lookup = mapping_icn_lookup
            icn_item = self.gd['icn'][mapping_icn_lookup]['widget']
            self.listWidget_ICNtemplates.setCurrentItem(icn_item)
        else:
            current_icn_lookup = None
        
        # Clear other lists & set default placement(s)
        if mapping_ica_lookup in self.gd['ica'].keys():
            ica_itemWidget = self.gd['ica'][mapping_ica_lookup]['widget']
            self.listWidget_ICAComponents.setCurrentItem(ica_itemWidget)
        elif current_ica_lookup in self.gd['ica'].keys():
            ica_itemWidget = self.gd['ica'][current_ica_lookup]['widget']
            self.listWidget_ICAComponents.setCurrentItem(ica_itemWidget)
        elif current_ica_lookup is None: #if ICA is deselected or no ICA is currently selected...
            self.listWidget_ICAComponents.setCurrentRow(-1)
        if mapping_icn_lookup in self.gd['icn'].keys():
            icn_itemWidget = self.gd['icn'][mapping_icn_lookup]['widget']
            self.listWidget_ICNtemplates.setCurrentItem(icn_itemWidget)
        elif current_icn_lookup in self.gd['icn'].keys():
            icn_itemWidget = self.gd['icn'][current_icn_lookup]['widget']
            self.listWidget_ICNtemplates.setCurrentItem(icn_itemWidget)
        elif current_icn_lookup is None: #if ICN is deslected or no ICN is currently selected...
            self.listWidget_ICNtemplates.setCurrentRow(-1)
            
        # Update GUI
        self.lineEdit_ICANetwork.setText(self.gd['mapped'][mapping_lookup]['ica_custom_name'])
        self.lineEdit_mappedICANetwork.setText(self.gd['mapped'][mapping_lookup]['icn_custom_name'])
        self.update_plots()

    def verify_existence(self, list_name, list_lookup=None, list_property='img'):
        """Checks for property (~spatial map/volume) in GUI data containers"""
        verdict = False
        if not list_lookup: return(verdict) #simplifies handling of None type
        if list_lookup in self.gd[list_name].keys():
            if list_property in self.gd[list_name][list_lookup].keys():
                if self.gd[list_name][list_lookup][list_property]:
                    verdict = True
        return(verdict)   
        
    def correlate_pair(self, ica_lookup=None, icn_lookup=None):
        """Correlate single pair of IC spatial & ICN template"""
        
        if not self.config['corr_onClick']:
            return #nothing to do
        ica_imgLoaded = self.verify_existence('ica', ica_lookup)
        icn_imgLoaded = self.verify_existence('icn', icn_lookup)
        if ica_imgLoaded and (ica_lookup not in self.corrs.keys()):
            self.corrs.update({ica_lookup : {}})
        if icn_imgLoaded and ica_imgLoaded:
            btn_txt = self.pushButton_runAnalysis.text()
            self.pushButton_runAnalysis.setText("Correlating...")
            if (ica_lookup in self.corrs.keys()) and (icn_lookup not in self.corrs[ica_lookup].keys()):
                reset_mapper = False
                if not hasattr(self, 'prbrGUI'):
                    reset_mapper = True
                elif ica_lookup not in self.prbrGUI.mapper.in_filenames:
                    reset_mapper = True
                elif icn_lookup not in self.prbrGUI.mapper.map_filenames:
                    reset_mapper = True
                if reset_mapper:
                    self.mapper = map.Mapper(map_files=self.get_imgs('icn'), 
                                                     map_filenames=self.get_img_names('icn'), 
                                                     in_files=self.get_imgs('ica'), 
                                                     in_filenames=self.get_img_names('ica'),
                                                     corrs=self.corrs)
                new_corrs = self.mapper.run_one(in_img_names=ica_lookup, 
                                                map_names=icn_lookup)

                ### Update existing Correlations ###
                for ica_lookup in new_corrs.keys():
                    if ica_lookup not in self.corrs.keys():
                        self.corrs.update({ica_lookup: {}})
                    self.corrs[ica_lookup].update(new_corrs[ica_lookup])
                    
            self.pushButton_runAnalysis.setText(btn_txt)
                    

    def repopulate_ICNs(self, ica_lookup=None):
        """Clear ICN list & re-populate w/ ranked items"""

        if not ica_lookup: return #nothing to do
        if self.listWidget_ICNtemplates.count() == 0:
            return  #if ICN list is empty, nothing to repopulate
        else:
            self.listWidget_ICNtemplates.clear()
        
        rank = 0
        if ica_lookup not in self.corrs.keys():
            self.corrs.update({ica_lookup : {}})
        for icn_lookup, ica_corr in sorted(self.corrs[ica_lookup].items(),
                                           key=lambda x:x[1], reverse=True):
            if icn_lookup and ica_corr:
                rank = rank+1
                item = QtWidgets.QListWidgetItem(icn_lookup)
                self.listWidget_ICNtemplates.addItem(item)
                item.setData(Qt.UserRole, icn_lookup)
                text = '%s.  %s   (%0.2f)' %(rank, self.gd['icn'][icn_lookup]['display_name'], 
                                             self.corrs[ica_lookup][icn_lookup])
                item.setText(text)
                self.gd['icn'][icn_lookup]['widget'] = item
                
        # Add slots for non-ranked, non-corr. ICNs & non-template ICNs/artifacts
        nonCorr_extras = [extra for extra in self.config['icn']['extra_items']]
        nonCorr_extras = nonCorr_extras + [extra for extra in self.config['noise']['extra_items']]
        nonCorr_extras = [extra for extra in nonCorr_extras if extra not in self.corrs[ica_lookup].keys()]
        nonCorr_icns = [icn_lookup for icn_lookup in self.gd['icn'].keys() if 
                       icn_lookup not in self.corrs[ica_lookup].keys()]
        nonCorr_icns = [icn_lookup for icn_lookup in nonCorr_icns if
                       icn_lookup not in nonCorr_extras]
        for icn_lookup in nonCorr_icns:
            item = QtWidgets.QListWidgetItem(icn_lookup)
            self.listWidget_ICNtemplates.addItem(item)
            item.setData(Qt.UserRole, icn_lookup)
            item.setText(self.gd['icn'][icn_lookup]['display_name'])
            self.gd['icn'][icn_lookup]['widget'] = item
        for extra in nonCorr_extras:
            item = QtWidgets.QListWidgetItem(extra)
            self.listWidget_ICNtemplates.addItem(item)
            item.setData(Qt.UserRole, extra)
            if extra in self.gd['icn'].keys():
                self.gd['icn'][extra]['widget'] = item


    
    #---------------------------------------------------
    ### Functions to handle mapped IC > ICN mappings ###
    #---------------------------------------------------
    def add_Classification(self, ica_icn_pair=None, ica_custom_name=None, 
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
        
        # Determine add item or update existing item
        rm_gd_entry = False # rm. gd entry w/ outdated info
        new_mapping_item = True # default to creating new item in mapping listwidget
        if (ica_lookup and icn_lookup):
            if ica_lookup in self.gd['mapped_ica'].keys():
                if icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                    rm_gd_entry = True # replace existing item w/ updated info
                    new_mapping_item = False # update existing listwidget item
                    updateGUI = False # no need to update display
                elif not self.config['ica']['allow_multiclassifications']:
                    rm_gd_entry = True # clear & replace item w/ new info
                    new_mapping_item = False # update existing listwidget item
                    updateGUI = False # no need to update display
        elif not (ica_lookup or icn_lookup):
            return # nothing selected, nothing to do

        # Update mapping info & list
        map_itemWidget = None
        if rm_gd_entry: # may be replaced w/ updated info later
            if icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                map_itemWidget = self.gd['mapped_ica'][ica_lookup][icn_lookup]
            else: # assume unique mapping to each ica key
                items = list(self.gd['mapped_ica'][ica_lookup].values())
                map_itemWidget = items[0]
            old_mapping_lookup = str(map_itemWidget.data(Qt.UserRole))
            del self.gd['mapped'][old_mapping_lookup]
        if new_mapping_item:
            map_itemWidget = QtWidgets.QListWidgetItem(mapping_lookup)
            self.listWidget_Classifications.addItem(map_itemWidget)
        if map_itemWidget:
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            map_itemWidget.setText(mapping_lookup)

        self.gd['mapped'].update({mapping_lookup: {'ica_lookup': ica_lookup,
                                                   'ica_custom_name': ica_custom_name,
                                                   'icn_lookup': icn_lookup,
                                                   'icn_custom_name': icn_custom_name,
                                                   'mapped_item' : map_itemWidget, }})
        
        # If ICA multiClass not enabled, remove ICA item from ICA listwidget
        if ica_lookup and not self.config['ica']['allow_multiclassifications']:
            ica_items = self.listWidget_ICAComponents.findItems(ica_lookup, Qt.MatchExactly)
            for ica_item in ica_items:
                self.listWidget_ICAComponents.takeItem(self.listWidget_ICAComponents.row(ica_item))
        
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
            self.listWidget_Classifications.setCurrentItem(map_itemWidget)
            self.update_gui_classifications(map_itemWidget)


    def delete_Classification(self):
        """Remove ICA > ICN mapping from list"""

        last_i = len(self.listWidget_Classifications.selectedItems()) - 1
        for i,item in enumerate(self.listWidget_Classifications.selectedItems()):
            mapping_lookup = str(item.data(Qt.UserRole))
            ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
            icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
            
            # Remove mapped widget item
            self.listWidget_Classifications.takeItem(self.listWidget_Classifications.row(item))
            self.listWidget_Classifications.clearSelection()
            
            # Remove data storage for mapping
            self.gd['mapped'].pop(mapping_lookup)

            # Update dict of mapped ICs/ICNs
            if icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                self.gd['mapped_ica'][ica_lookup].pop(icn_lookup)
            if len(self.gd['mapped_ica'][ica_lookup].keys()) == 0:
                self.gd['mapped_ica'].pop(ica_lookup)
            if ica_lookup in self.gd['mapped_icn'][icn_lookup].keys():
                self.gd['mapped_icn'][icn_lookup].pop(ica_lookup)
            if len(self.gd['mapped_icn'][icn_lookup].keys()) == 0:
                self.gd['mapped_icn'].pop(icn_lookup)
                
            # Add ICA item back to listwidget
            if ica_lookup in self.gd['ica'].keys():
                ica_display_name = self.gd['ica'][ica_lookup]['display_name']
                ica_matches = self.listWidget_ICAComponents.findItems(ica_display_name, 
                                                                      Qt.MatchExactly)
                if len(ica_matches) == 0:
                    ica_item = QtWidgets.QListWidgetItem(ica_lookup)
                    self.listWidget_ICAComponents.addItem(ica_item)
                    ica_item.setData(Qt.UserRole, ica_lookup)
                    ica_item.setText(self.gd['ica'][ica_lookup]['display_name'])
                    self.gd['ica'][ica_lookup]['widget'] = ica_item
                    
                    if i == last_i:
                        self.listWidget_ICAComponents.setCurrentItem(ica_item)
                        self.update_gui_ica(ica_item)
            elif i == last_i:
                    self.update_plots()
                                
                
    def find_duplicate_mappings(self, duplicated_name='ica'):
        """Find ICA comps/ICN templates, etc. in multiple mappings/classifications,
        without taking into account customized names"""
        
        if duplicated_name not in ['ica', 'icn']: return #nothing to do
        
        self.listWidget_Classifications.clearSelection()
        self.listWidget_Classifications.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        if duplicated_name == 'ica':
            mapped_list = 'mapped_ica'
            dup_type = 'ICA comp.'
            dup_type_other = 'ICNs'
            extras = None
        elif duplicated_name == 'icn':
            mapped_list = 'mapped_icn'
            dup_type = 'ICN template'
            dup_type_other = 'ICA comps.'
            extras = [k for k in self.gd['icn'].keys() if re.match('\\.*noise', k, flags=re.IGNORECASE)]
            extras += self.config['icn']['extra_items'] 
            extras += self.config['noise']['extra_items']
        else:
            dup_type = duplicated_name.capitalize()
            custom_names = []
            extras = None
            
        mappings_dup_names = []
        mappings_dup_items = []
        found_duplicates = False
        for lookup1 in self.gd[mapped_list].keys():
            if ((lookup1 not in extras) and 
                  (len(self.gd[mapped_list][lookup1]) >= 2)):
                for lookup2 in self.gd[mapped_list][lookup1].keys():
                    found_duplicates = True
                    mapping_item = self.gd[mapped_list][lookup1][lookup2]
                    mapping_item.setSelected(True)
                    mappings_dup_items.append(mapping_item)
                    mappings_dup_names.append(str(mapping_item.text()))
                   
        if not found_duplicates:
            title = "Searching for multiple "+ dup_type +" classifications:"
            message = "No multiclassifications found, all current "
            message += dup_type +" classifications are unique"
            QtWidgets.QMessageBox.information(self, title, message)
        else:
            title = "Searching for multiple "+ dup_type +" classifications:"
            message = "Found multiple classifications of "+ dup_type +"s to multiple "
            message += dup_type_other + ":"
            for i,mapping in enumerate(mappings_dup_names):
                message += "\n   " + mapping
            message += "\n\n(Note: above may include duplicated " + dup_type
            message +=  " items under multiple customized, unique names)"
            message += "\n\nContinue to 'select classifications' window to remove & reset above items?"
            
            if QtWidgets.QMessageBox.question(None, title, message,
                                              QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                              QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                self.clear_list_select(list_name='mapped', 
                                       listWidget=self.listWidget_Classifications,
                                       list_subset = mappings_dup_items)
        self.listWidget_Classifications.clearSelection()
        self.listWidget_Classifications.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
                           
                   
    def find_probable_classifications(self):
        """Find obvious, unambigous/undisputed possible mappings for non-classified ICA comps"""
        
        warnflag = False
        title = "Finding likely classifications:"
        if not hasattr(self, 'corrs'):
            warnflag = True
        elif not self.corrs:
            warnflag = True
        if warnflag:
            message = "Correlations need to be calculated in order to find likely classifications"
            QtWidgets.QMessageBox.warning(self, title, message)
            return
        
        # Definitions of "Obvious" & "Undisputed" Criteria: 
        min_corr = 0.3  # minimum top corr. > 0.3
        unambig_factor = 2 # top corr must be at least twice the corr for 2nd-highest match
        criteria = "Criteria: \n1. ICA comp. strongly matches template (r > " + str(min_corr) + ")"
        criteria += " \n2. ICN template currently without comparable alternatives"
        criteria += " \n(defined as top match "+str(unambig_factor)+"x or more than all other corrs.):"

        self.matches = map.Mapper.assign_matches(self.get_img_names('ica'), 
                                                 self.corrs, 
                                                 min_corr=min_corr,
                                                 unambigous_scaling_factor=unambig_factor)
        # Select possible mappings to add
        new_mappings = []
        conflicting_mappings = []
        redundant_mappings = []
        mapping_info = {}
        for ica_lookup, icn_lookup in self.matches.items():
            if ica_lookup and icn_lookup:
                ica_custom_name = self.gd['ica'][ica_lookup]['display_name']
                icn_custom_name = self.gd['icn'][icn_lookup]['display_name']
                potential_mapping = "%s > %s" %(ica_custom_name, icn_custom_name)
                mapping_info.update({potential_mapping: {'ica_lookup': ica_lookup,
                                         'icn_lookup': icn_lookup,
                                         'ica_custom_name':ica_custom_name,
                                         'icn_custom_name':icn_custom_name}})
                
                # Sort potential new mappings
                if potential_mapping in self.gd['mapped'].keys():
                    redundant_mappings.append(potential_mapping) #mapping already exists, ignore
                else:
                    if ica_lookup in self.gd['mapped_ica'].keys():
                        if ((not self.config['ica']['allow_multiclassifications']) and
                             (icn_lookup not in self.gd['mapped_ica'][ica_lookup].keys())):
                            #ICA mappings must be unique, pairing w/ new ICN will overwrite existing mapping
                            conflicting_mappings.append(potential_mapping)
                        elif icn_lookup not in self.gd['mapped_ica'][ica_lookup].keys():
                            new_mappings.append(potential_mapping) #new ICA>ICN pair, consider adding
                        else:
                            redundant_mappings.append(potential_mapping) #ICA>ICN pair exists by another name
                    else:
                        new_mappings.append(potential_mapping) #unmapped ICA comp., consider adding
                        
        if len(new_mappings) + len(conflicting_mappings) == 0:
            message = "No potential classifications found."
            message += "\n\nAll currently unclassified ICA comps. "
            message += "either feature weak (r < " + str(min_corr) + ") top matches,"
            message += " or ambigous matching to multiple templates"
            QtWidgets.QMessageBox.information(self, title, message)
            return
        message = ""
        if len(new_mappings) > 0:
            message += "Found likely new classifications:"
            for mapping in new_mappings:
                message += "\n   " + mapping
            message += "\n\n"
        if len(conflicting_mappings) > 0:
            message += "Found likely classifactions,"
            message += " but will override existing classifications:"
            for mapping in conflicting_mappings:
                message += "\n   " + mapping
            message += "\n\n"
        if len(new_mappings) + len(conflicting_mappings) > 0:
            message += criteria
            message += "\n\nContinue to 'select mappings' to add from above?"
            if QtWidgets.QMessageBox.question(None, title, message,
                                              QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                              QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                
                new_mappings += conflicting_mappings
                self.selectionWin = select.newSelectWin(self.listWidget_Classifications, 
                                                        title="Select classifications to add:", 
                                                        add_items = new_mappings,
                                                        list_subset=[]) #empty subset excludes current list items
                
                if self.selectionWin.accept_result == QtWidgets.QDialog.Accepted:
                    for mapping_lookup in self.selectionWin.selected_display_names:
                        ica_lookup = mapping_info[mapping_lookup]['ica_lookup']
                        icn_lookup = mapping_info[mapping_lookup]['icn_lookup']
                        ica_custom_name = mapping_info[mapping_lookup]['ica_custom_name']
                        icn_custom_name = mapping_info[mapping_lookup]['icn_custom_name']
                        self.add_Classification(ica_icn_pair=(ica_lookup, icn_lookup), 
                                                ica_custom_name=ica_custom_name,
                                                icn_custom_name=icn_custom_name, 
                                                updateGUI=False)
                    self.update_plots()            
                   
                   
    def find_questionable_classifications(self):
        """Find mappings between low-correlated ICA & ICN pairs,
        Pull up GUI to allow rethinking/removal"""
        
        min_corr = 0.3       # ...r < 0.3 is suspect
        unambig_factor = 2   # ...top matches less than 2x as high as next highest are disputable
        suspect_lookups = []
        suspect_items = []
        self.listWidget_Classifications.clearSelection()
        self.listWidget_Classifications.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)

        for mapping_lookup in self.gd['mapped'].keys():
            ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
            icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
            if ica_lookup in self.corrs.keys():
                if icn_lookup in self.corrs[ica_lookup].keys():
                    if self.corrs[ica_lookup][icn_lookup] < min_corr:
                        suspect_lookups.append(mapping_lookup)
                    else:
                        other_corrs = self.corrs[ica_lookup].copy()
                        del other_corrs[icn_lookup]
                        best_other_corr = max(other_corrs.values())                        
                        if self.corrs[ica_lookup][icn_lookup] < best_other_corr * unambig_factor:
                            suspect_lookups.append(mapping_lookup)
                            
        if len(suspect_lookups) > 0:
            title = "Searching for weak or debatable classifications in mappings:"
            message = "Found weak (r < "+ str(min_corr)  +") or depatable (r1 ~ r2) mappings:\n"
            for i,mapping in enumerate(suspect_lookups):
                message += "\n   " + mapping
                mapping_item = self.gd['mapped'][mapping]['mapped_item']
                mapping_item.setSelected(True)
                suspect_items.append(mapping_item)
            message += "\n\nContinue to 'select mappings', to reset & re-classify?"
            if QtWidgets.QMessageBox.question(None, title, message,
                                              QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                              QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                self.clear_list_select(list_name='mapped', 
                                       listWidget=self.listWidget_Classifications,
                                       list_subset = suspect_items)
        
        self.listWidget_Classifications.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.update_plots()

       
    #--------------------------------------------------------
    ### Functions used to plot spatial maps & time series ###
    #--------------------------------------------------------
    def update_plots(self):
        """Update plots using global plotting options"""

        ica_lookup, icn_lookup = self.get_current_networks()
        if ica_lookup or icn_lookup:
            options = self.get_plot_options(ica_lookup, icn_lookup, coords_from_sliders=False)
            self.plot_vols(self.figure_x, **options)
            self.canvas_x.draw()
            self.plot_time(self.figure_t, **options)
            self.canvas_t.draw()
            
    def update_plots_from_sliders(self):
        """Updates plots after change in x,y,z slider bars,
        without changing global plotting options"""
        
        ica_lookup, icn_lookup = self.get_current_networks()
        if ica_lookup or icn_lookup:
            options = self.get_plot_options(ica_lookup, icn_lookup, coords_from_sliders=True)
            self.plot_vols(self.figure_x, **options)
            self.canvas_x.draw()
            self.plot_time(self.figure_t, **options)
            self.canvas_t.draw()
            
    def get_current_networks(self):
        """Determine which ICs & ICN templates, or mappings are currently selected"""
        if self.listWidget_Classifications.currentRow() != -1:
            mapping_lookup = str(self.listWidget_Classifications.currentItem().data(Qt.UserRole))
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
            self.reset_display()
        return ica_lookup, icn_lookup
            
    def get_plot_options(self, ica_lookup, icn_lookup, coords_from_sliders=False):
        """Get all plot options"""
        
        displayLayout, coords = self.apply_slice_views(ica_lookup, icn_lookup, coords_from_sliders)
        options = {'ica_lookup': ica_lookup, 
                   'icn_lookup': icn_lookup, 
                   'displayLayout': displayLayout, 
                   'coords': coords}
        options.update({'show_icn': self.mp['icn']['show_icn']})
        if icn_lookup in self.gd['icn'].keys():
            if not isinstance(self.gd['icn'][icn_lookup]['img'], (Nifti1Image, Nifti1Pair)):
                options.update({'show_icn': False})
        else:
            options.update({'show_icn': False})
        options.update({'show_time_series': self.tp['items']['show_time_series']})
        options.update({'show_spectrum': self.tp['items']['show_spectrum']})
        
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
        
        # default options
        layout = 'ortho' #default to 3 orthogonal slices
        coords = (x, y, z) #default to current coords
        
        # Get layout & sha. of display matrix
        num_rows = self.mp['global']['num_rows']
        num_cols = self.mp['global']['num_cols']
        num_slices = num_rows * num_cols
        layout = self.mp['global']['display_mode']
        
        if layout == 'ortho':
            self.pushButton_showMaxOverlap.setEnabled(True)
            self.horizontalSlider_Xslice.setEnabled(True)
            self.horizontalSlider_Yslice.setEnabled(True)
            self.horizontalSlider_Zslice.setEnabled(True)
            displayLayout = 'ortho'
            if masked_img and not coords_from_sliders:
                x, y, z = plotting.find_xyz_cut_coords(masked_img, activation_threshold=None)
                self.get_and_set_slice_coordinates(x, y, z)
            coords = (x, y, z)
        elif layout == 'axial':
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            displayLayout = 'z'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='z', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=None, y=None, z=coords)
        elif layout == 'coronal':
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            displayLayout = 'y'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='y', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=None, y=coords, z=None)
        elif layout == 'sagittal':
            self.pushButton_showMaxOverlap.setEnabled(False)
            self.horizontalSlider_Xslice.setEnabled(False)
            self.horizontalSlider_Yslice.setEnabled(False)
            self.horizontalSlider_Zslice.setEnabled(False)
            displayLayout = 'x'
            if masked_img:
                coords = plotting.find_cut_slices(masked_img, direction='x', n_cuts=num_slices)
                self.get_and_set_slice_coordinates(x=coords, y=None, z=None)
        return displayLayout, coords
        

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

    def arrange_slices(self, displayLayout, coords, grid=False): 
        """Arrange slices in display, into ~rectangle determined by number slices"""
        
        if displayLayout in ['ortho','tiled']:
            return 'ortho', [coords]  #use nilearn plotting fns. for layout
        elif not self.mp['global']['grid_layout']:
            return displayLayout, [coords] # plot slices in single row
        
        num_slices = len(coords)
        if grid:
            num_rows = self.mp['global']['num_rows']
        else: num_rows = 1
        num_cols = num_slices // num_rows  #see 'apply_slice_views' for padding rows w/ extra coords
        coords_byRow = []
        start = 0
        end = 0
        for row in range(num_rows):
            start = end
            end = start + num_cols
            coords_byRow.insert(0, coords[start:end])
            
        return displayLayout, coords_byRow

    
    def figure_x_onClick(self, event):
        """Click to change MNI coords on spatial map display"""
        
        if self.buttonGroup_xview.checkedButton() == self.radioButton_ortho:
            if event.inaxes is None:
                return
            elif event.inaxes == self.figure_x.axes[1]: #coronal section, based on plotting limits ~ MNI coords
                x = event.xdata
                y = self.horizontalSlider_Yslice.value()
                z = event.ydata
            elif event.inaxes == self.figure_x.axes[2]: #sagittal section
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
        

    def plot_vols(self, fig, ica_lookup, icn_lookup, displayLayout='ortho', coords=(0,0,0), *args, **kwargs):
        """Default spatial map plotting"""
        
        # Required parameters
        if 'show_colorbar' in kwargs.keys():
            show_colorbar = kwargs['show_colorbar']
        else:
            show_colorbar = self.mp['global']['show_colorbar']
        if 'show_LR_annotations' in kwargs.keys():
            show_LR_annotations = kwargs['show_LR_annotations']
        else:
            show_LR_annotations = self.mp['global']['show_LR_annotations']
        if 'show_crosshairs' in kwargs.keys():
            show_crosshairs = kwargs['show_crosshairs']
        else:
            show_crosshairs = self.mp['global']['crosshairs']
        if 'thresh_ica_vol' in kwargs.keys():
            thresh_ica_vol = kwargs['thresh_ica_vol']
        else:
            thresh_ica_vol = self.mp['ica']['thresh_ica_vol']
        if 'ica_vol_thresh' in kwargs.keys():
            ica_vol_thresh = kwargs['ica_vol_thresh']
        else:
            ica_vol_thresh = self.mp['ica']['ica_vol_thresh']
        if 'show_icn' in kwargs.keys():
            show_icn = kwargs['show_icn']
        else:
            show_icn = self.mp['icn']['show_icn']
        if 'show_mapping_name' in kwargs.keys():
            show_mapping_name = kwargs['show_mapping_name']
        else:
            show_mapping_name = self.mp['global']['show_mapping_name']
        if 'show_ica_name' in kwargs.keys():
            show_ica_name = kwargs['show_ica_name']
        else:
            show_ica_name = self.mp['global']['show_ica_name']
        if 'show_icn_name' in kwargs.keys():
            show_icn_name = kwargs['show_icn_name']
        else:
            show_icn_name = self.mp['global']['show_icn_name']
        
        # Get required vols.
        anat_img = None
        if self.mp['anat']['file']: # temporarily load sMRI vol for display
            anat_img = self.io.load_single_file(self.mp['anat']['file'], 
                                                file_type='smri', temporary=True)
        if not anat_img:
            anat_img = self.gd['smri']['img']
        if ica_lookup:
            stat_img = self.gd['ica'][ica_lookup]['img']
        elif icn_lookup:
            stat_img = self.gd['icn'][icn_lookup]['img']
            show_icn = False
        else:
            return    #nothing to plot
        if stat_img is None:
            return    #nothing to plot

        thresh = None
        if thresh_ica_vol and ica_vol_thresh:
            if 1e-06 < ica_vol_thresh < 1:
                thresh = np.nanmax(np.absolute(stat_img.get_fdata())) * ica_vol_thresh
            else: thresh = thresh_ica_vol
        if not thresh or not isinstance(thresh, Number):
            thresh = 1e-06 # NOTE: thresh = None prevents plotting of anatomical background
            
        # Prepare figure space & clear old plots from mem.
        fig.clear()
        if 'd_opened' not in locals():
            d_opened = [] # store list of open plots, in need of closing...
        else:             # manually close all open nilearn plots, prevent accumulation in memory
            for d in d_opened:
                d.close()  
                d_opened.remove(d)
                
        # Arrage layout of slices
        displayLayout, coords_byRow = self.arrange_slices(displayLayout, coords,
                                                          grid=self.mp['global']['grid_layout'])
        num_rows = len(coords_byRow)        
        
        # Multi-row plotting
        for row in range(num_rows):
            ax1 = fig.add_subplot(num_rows,1,row+1) if isinstance(fig, Figure) else fig

            d = plotting.plot_stat_map(stat_map_img=stat_img, bg_img=anat_img, 
                                       axes=ax1, cut_coords=coords_byRow[row], 
                                       display_mode=displayLayout, 
                                       threshold=thresh,
                                       draw_cross=show_crosshairs, 
                                       annotate=show_LR_annotations, 
                                       colorbar=show_colorbar)
            if show_icn and isinstance(self.gd['icn'][icn_lookup]['img'], 
                                       (Nifti1Image, Nifti1Pair)):
                d.add_contours(self.gd['icn'][icn_lookup]['img'], 
                               filled=self.mp['icn']['filled'], 
                               alpha=self.mp['icn']['alpha'], 
                               levels=[self.mp['icn']['levels']], colors=self.mp['icn']['colors'])
            ax1.set_axis_off()
           
            # nilearn fine print: plots accumulate in memory, not automatically cleared...
            d_opened.append(d) # ...store running list of plots in use 
            
#         ### Single row plotting ###
#         fig.clear()
#         if 'd' in locals(): d.close() # plots need to be manually close, or will accumulate in memory
#         ax1 = fig.add_subplot(111) if isinstance(fig, Figure) else fig
        
#         d = plotting.plot_stat_map(stat_map_img=stat_img, bg_img=anat_img, 
#                                    axes=ax1, cut_coords=coords, 
#                                    display_mode=displayLayout, threshold=thresh,
#                                    draw_cross=show_crosshairs, 
#                                    annotate=True, colorbar=True)
#         if show_icn and isinstance(self.gd['icn'][icn_lookup]['img'], 
#                                    (Nifti1Image, Nifti1Pair)):
#             d.add_contours(self.gd['icn'][icn_lookup]['img'], 
#                            filled=self.mp['icn']['filled'], 
#                            alpha=self.mp['icn']['alpha'], 
#                            levels=[self.mp['icn']['levels']], 
#                            colors=self.mp['icn']['colors'])
#         ax1.set_axis_off()
        
        if show_mapping_name or show_ica_name or show_icn_name:
            display_text = ''
            ica_custom_name = None
            icn_custom_name = None
            if ica_lookup in self.gd['ica'].keys():
                ica_custom_name = self.gd['ica'][ica_lookup]['display_name']
            if icn_lookup in self.gd['icn'].keys():
                icn_custom_name = self.gd['icn'][icn_lookup]['display_name']
            if show_mapping_name:
                if ((ica_lookup in self.gd['mapped_ica'].keys()) and
                      (icn_lookup in self.gd['mapped_ica'][ica_lookup].keys())):
                    map_item = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                    mapping_lookup = str(map_item.data(Qt.UserRole))
                    display_text = self.gd['mapped'][mapping_lookup]['icn_custom_name']
                elif icn_custom_name:
                    display_text = icn_custom_name
                elif ica_custom_name:
                    display_text = ica_custom_name
            if show_ica_name and ica_custom_name:
                display_text += '\n   ICA component:   %s' % ica_custom_name
            if show_icn_name and icn_custom_name:
                display_text += '\n   ICN template:   %s' % icn_custom_name
            if isinstance(fig, Figure):
                x_pos, y_pos = (0.07, 0.99)
            else:
                _, y_pos = fig.get_ylim()
                y_pos = y_pos - 0.01
                x_pos, _ = fig.get_xlim()
            fig.text(x_pos,y_pos, display_text, 
                     color='white', size=self.mp['global']['display_text_size'],
                     horizontalalignment='left', verticalalignment='top')
        if isinstance(fig, Figure):
            fig.tight_layout(pad=0)
            
    def plot_time(self, fig=None, ica_lookup=None, coords=(0,0,0), *args, **kwargs):
        """Default time series plotting"""
        
        if 'ax_handles' not in kwargs.keys():
            fig.clear() # clear existing time series plots in GUI display
        if 'show_time_series' in kwargs.keys():
            show_time_series = kwargs['show_time_series']
        else:
            show_time_series = self.tp['items']['show_time_series']
        if 'show_spectrum' in kwargs.keys():
            show_spectrum = kwargs['show_spectrum']
        else:
            show_spectrum = self.tp['items']['show_spectrum']
        if 'sampling_rate' in kwargs.keys():
            Fs = kwargs['sampling_rate']
        else:
            Fs = self.tp['global']['sampling_rate']

        # No plots-to-render conditions
        if not show_time_series and not show_spectrum:
            return
        elif not ica_lookup:
            return  
        elif 'timeseries' not in self.gd['ica'][ica_lookup].keys():
            return
        elif self.gd['ica'][ica_lookup]['timeseries'] is None:
            return
        elif self.gd['ica'][ica_lookup]['timeseries'].ndim > 1:
            return
        
        # Determine Axes Layout
        if 'ax_handles' in kwargs.keys():
            ax_handles = kwargs['ax_handles']
            axts = ax_handles['axts'] if 'axts' in ax_handles.keys() else None
            axps = ax_handles['axps'] if 'axps' in ax_handles.keys() else None
        else: # set up a 2 rows by 5 columns subplot layout, within overall time series subplot itself
            if isinstance(fig, gridspec.GridSpec):
                gs = gridspec.GridSpecFromSubplotSpec(2, 5, fig)
            else:
                gs = gridspec.GridSpec(2, 5)
                
            if show_time_series and show_spectrum: 
                axts, axps = plt.subplot(gs[:, 3:]), plt.subplot(gs[:, :3])
            elif not show_time_series and show_spectrum:
                axps = plt.subplot(gs[:, :])  # handle for powerspectrum subplots 
            elif show_time_series and not show_spectrum:
                axts = plt.subplot(gs[:, :])  # handle for single time series subplot
        if show_time_series:
            ts = self.gd['ica'][ica_lookup]['timeseries']
            n = len(ts)
            axts.plot(np.arange(0,n*Fs,Fs), ts)
            axts.spines['right'].set_visible(False)
            axts.spines['top'].set_visible(False)
            axts.set_title('ICA Time-Series')
            axts.set_xlabel('Time (s)')
            axts.set_ylabel('fMRI signal')
            axts.set_facecolor('White')
        if show_spectrum:
            n = len(self.gd['ica'][ica_lookup]['timeseries'])
            ps = np.fft.rfft(self.gd['ica'][ica_lookup]['timeseries'], norm='ortho')
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

    app = QtWidgets.QApplication(sys.argv)
    form = NetworkZooGUI(configuration_file=config_file)
    form.show()  # Show the form
    app.exec()  # and execute the app


if __name__ == '__main__': 
    main(sys.argv[1:])
        
        
        
