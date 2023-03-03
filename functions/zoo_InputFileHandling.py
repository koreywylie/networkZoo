# Python Libraries
from os.path import join as opj  # method to join strings of file paths
import os, sys, re, json, csv

# Qt GUI Libraries
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt


# Mathematical/Neuroimaging/Plotting Libraries
import numpy as np
from nilearn import plotting, image  # library for neuroimaging
from nibabel.nifti1 import Nifti1Image, Nifti1Pair
import nipype.interfaces.io as nio


class InputHandling(object):
    """Fns. to handle input/output, file loading, etc., for Network Zoo"""
    
    def __init__(self, gd, config, corrs,
                 listWidget_ICA, listWidget_ICN, listWidget_mapped):
        super().__init__()
        
        # Connections to data containers in Network Zoo script
        self.gd = gd # NetworkZooGUI.gd
        self.config = config # NetworkZooGUI.config
        self.corrs = corrs # NetworkZooGUI.corrs
        
        # Connections to Qt items in main window
        self.listWidget_ICA = listWidget_ICA # NetworkZooGUI.listWidget_ICAComponents
        self.listWidget_ICN = listWidget_ICN # NetworkZooGUI.listWidget_ICNtemplates
        self.listWidget_mapped = listWidget_mapped # NetwokrZooGUI.listWidget_mappedICANetworks
    
    def get_item_prop(self, list_name, list_property):
        """Get item's properties from networkZoo list"""
        return [item[list_property] for item in self.gd[list_name].values()]

        
    def configure_ICs(self):
        """Load anatomical file, ICA comps, ICN & noise templates on startup"""
        
        if os.path.isfile(self.config['smri_file']):
            self.load_single_file(self.config['smri_file'], file_type='smri')
        if os.path.exists(self.config['ica']['directory']):
            ica_files = self.find_files(self.config['ica']['directory'], 
                                        self.config['ica']['template'],
                                        self.config['ica']['search_pattern'],
                                        list_name='ica')
            self.load_ica_timeseries(ica_files=ica_files,
                                     prompt_fileDialog=False, search_toolbox_output=True)
        if os.path.exists(self.config['icn']['directory']):
            self.find_files(self.config['icn']['directory'], 
                            self.config['icn']['template'], 
                            self.config['icn']['search_pattern'],
                            list_name='icn', 
                            extra_items=self.config['icn']['extra_items'])
        else:
            for extra in self.config['icn']['extra_items']:
                if extra not in self.gd['icn'].keys():
                    self.update_file_info('icn', None, None, self.listWidget_ICN,
                                          lookup_key=extra)
        if os.path.exists(self.config['noise']['directory']):
            self.find_files(self.config['noise']['directory'], 
                            self.config['noise']['template'], 
                            self.config['noise']['search_pattern'],
                            list_name='icn', 
                            extra_items=self.config['noise']['extra_items'])
        else:
            for extra in self.config['noise']['extra_items']:
                if extra not in self.gd['icn'].keys():
                    self.update_file_info('icn', None, None, self.listWidget_ICN,
                                          lookup_key=extra)


    def load_noise_templates(self):
        """Load noise templates"""
        
        os.chdir(self.config['base_directory'])
        self.find_files(self.config['noise']['directory'], 
                        self.config['noise']['template'], 
                        self.config['noise']['search_pattern'], 
                        list_name='icn', 
                        extra_items=self.config['noise']['extra_items'])  

    def load_demo_files(self, demo_ica_path):
        """Demo ICA run from Smith et al. 2009 (w/o timeseries)"""
        
        ica_files = self.find_files(os.path.dirname(demo_ica_path), 
                                    self.config['ica']['template'], 
                                    self.config['ica']['search_pattern'],
                                    list_name='ica')
        self.load_ica_timeseries(ica_files=ica_files, 
                                 prompt_fileDialog=False, search_toolbox_output=True)

    def load_single_file(self, file_name, file_type='fmri', temporary=False):
        """Load single MRI/fMRI vol & add to appropriate list.
        For simpler file types (~anatomical vol.)"""
        
        old_full_path = None
        old_img = None
        if hasattr(self, 'gd'):
            if file_type in self.gd.keys():
                old_full_path = self.gd[file_type]['full_path']
                old_img = self.gd[file_type]['img']
        ok = False
        if os.path.isfile(file_name):
            if os.path.splitext(file_name)[-1] in ['.img', '.hdr', '.nii']:
                ok = True
            elif os.path.splitext(file_name)[-1] in ['.gz']:
                file_name2 = os.path.splitext(file_name)[-2]
                if os.path.splitext(file_name2)[-1] in ['.img', '.hdr', '.nii']:
                    ok = True
        if ok and temporary:  # just return img, for temporary display
            return image.load_img(str(file_name))
        elif temporary:
            return None
        elif ok:
            self.gd.update({file_type: {'full_path': file_name, 
                                        'img': image.load_img(str(file_name))}})
        else:
            self.gd.update({file_type: {'full_path': old_full_path,
                                        'img': old_img}})
    
    def browse_files(self, title='Select Files', directory='.', filter=''):
        """GUI File browser to load multiple files"""
        
        selected_files = QtWidgets.QFileDialog.getOpenFileNames(None, title, directory, filter)
        selected_files = selected_files[0] #discards filter info contained in 2nd element of tuple
        selected_files = [str(f) for f in selected_files if isinstance(f, str)]
        selected_files.sort()
        return(selected_files)        
                
        
    def find_files(self, directory, template, search_pattern, list_name, 
                   exclude_pattern=None, extra_items=None):
        """GUI-less loading of files & find csv w/ custom names"""
        
        if list_name == 'ica':
            listWidget = self.listWidget_ICA
        elif list_name == 'icn':
            listWidget = self.listWidget_ICN
        
        if directory:
            if os.path.isfile(directory):
                found_files = [directory]
            else:
                ds = nio.DataGrabber(base_directory=directory, template=template, sort_filelist=True)
                found_files = ds.run().outputs.outfiles
                                
            self.add_files_to_list(listWidget, list_name, 
                                   found_files, None, 
                                   search_pattern, exclude_pattern, extra_items)
            
            # Load replacement IC labels stored in csv file, if applicable
            if search_pattern is not None:
                r_pattern = re.compile(search_pattern)
                found_files = [f for f in filter(r_pattern.search, found_files)]
            if len(found_files) > 0:
                if os.path.splitext(found_files[0])[-1] in ['.img', '.hdr', '.nii']:
                    csv_fname = os.path.splitext(found_files[0])[0] + '.csv'
                elif os.path.splitext(found_files[0])[-1] not in ['.nii.gz']:
                    csv_fname = os.path.splitext(found_files[0])[0]
                    csv_fname = os.path.splitext(csv_fname)[0] + '.csv'
                if os.path.isfile(csv_fname):
                    self.load_ic_customNames(csv_fname, list_name)
                return(found_files)
        
    
    def add_files_to_list(self, listWidget, list_name, files_to_add, file_inds=None, 
                          search_pattern='*', exclude_pattern=None, extra_items=None, append=True):
        """Add files to list & format info for parsing w/ networkZoo"""
        
        if not append: # Used when loading saved analyses
            listWidget.clear() # ...in case there are any existing elements in the list
            self.gd[list_name] = {}
        files_to_add = [f for f in files_to_add if f is not None]
        
        if len(files_to_add) > 1:
            files_to_add = list(set(files_to_add))  #remove duplicate entires for 4D nifti files
            files_to_add.sort()
        if search_pattern is not None:
            r_pattern = re.compile(search_pattern)
            files_to_add = [f for f in filter(r_pattern.search, files_to_add)]
        if exclude_pattern is not None:
            ex = re.compile(exclude_pattern)
            exclude_files = [f for f in filter(ex.search, files_to_add)]
            filtered_files = [f for f in files_to_add if f not in exclude_files]
        else:
            filtered_files = files_to_add
            
        for file_name in filtered_files:
            if os.path.isfile(file_name):
                img_vol = image.load_img(file_name)
                vol_dim = len(img_vol.shape)
                if vol_dim == 3:
                    k_range = range(1)
                elif vol_dim > 3:
                    k_range = range(img_vol.shape[3])
                if file_inds: #index individual vols w/n 4d vol., or 3d vol. indexed by intensities
                    if file_name in file_inds.keys():
                        k_range = [int(float(k)) for k in file_inds[file_name].keys()]

                error_message = None
                if vol_dim < 3: #if 2D nifti choosen by mistake...
                    img_vol.uncache()
                    error_message = "2D nifti file or GIFT time series file choosen/entered,"
                elif vol_dim > 3: 
                    # iter_img() preferred over index_img() for repeated img indexing
                    for k, img in enumerate(image.iter_img(img_vol)):
                        if k not in k_range: continue
                        self.update_file_info(list_name, file_name, img, listWidget,
                                              k=k, k_range=k_range, file_inds=file_inds, 
                                              vol_dim=vol_dim, r_pattern=r_pattern)
                elif vol_dim == 3: # iter_img() not applicable to non-4D volumes
                    self.update_file_info(list_name, file_name, img_vol, listWidget,
                                          k=0, k_range=k_range, file_inds=file_inds, 
                                          vol_dim=vol_dim, r_pattern=r_pattern)
                    
                    # if all intensities in img are integers w/ few unique values...
                    v_unique = np.unique(img_vol.get_fdata(caching='unchanged'))
                    if (all(v_unique >= 0) and (2 < len(v_unique) < 1000) and 
                        (np.mod(v_unique,1) == 0).all()): # if all integers
                        
                        # ...expand contents of ROI atlas as separate list items
                        self.expand_ROI_atlas_vol(file_name, 
                                                  list_name=list_name, listWidget=listWidget)
                else:
                    error_message = "Could not understand Nifti volume"
                if error_message:
                    title = "Error loading Nifti volumes"
                    error_message += " please select 3D or 4D nifti files"
                    QtWidgets.QMessageBox.warning(None, title, error_message)

        
        if extra_items:
            for extra in extra_items:
                if extra not in self.gd[list_name].keys():
                    self.update_file_info(list_name, None, None, listWidget,
                                          lookup_key=extra)
                         
        if file_inds: # replace default names, if provided
            self.replace_ic_customNames(file_inds, list_name, listWidget)
                    
        listWidget.clearSelection()  # does not change current item, but paradoxically deselects it
        listWidget.setCurrentRow(-1) # deselect everything
        
        
    def update_file_info(self, list_name, file_name, img, listWidget, 
                         lookup_key=None, widget_item=None, display_name=None,
                         k=0, k_range=None, file_inds=None, vol_dim=3, r_pattern=None):
        """Creates/updates lookup_key for Qt widget & self.gd entry for item info"""
        
        lookup_default = lookup_key # check lookup_key before accepting
        if not lookup_default:
            if file_inds: # use input dict entry as default key
                if file_name in file_inds.keys():
                    if str(k) in file_inds[file_name].keys():
                        lookup_default = file_inds[file_name][str(k)] 
            else: # use input file name as default key, after tweaking
                lookup_default = file_name 
                if r_pattern is not None:
                    match = re.search(r_pattern, lookup_default)
                    if match: lookup_default = match.groups()[0]
                if k_range:
                    if len(k_range) > 1:
                        lookup_default = lookup_default + ',%d' %(int(k)+1)
                        
        if lookup_default in self.gd[list_name].keys(): # verify info for default
            display_name = lookup_default  # default replaced below
            lookup_key = lookup_default + '_' # add suffix to create unique key, replaced below
            if ((file_name == self.gd[list_name][lookup_default]['filepath']) and 
                (int(k) == self.gd[list_name][lookup_default]['vol_ind'])):
                lookup_key = lookup_default # use existing key w/ verified info
                widget_item = self.gd[list_name][lookup_key]['widget']
                display_name = self.gd[list_name][lookup_key]['display_name']
            else:
                file_names_list = self.get_item_prop(list_name, 'filepath')
                if file_name in file_names_list:
                    for key in self.gd[list_name].keys():
                        if ((file_name == self.gd[list_name][key]['filepath']) and 
                            (int(k) == self.gd[list_name][key]['vol_ind'])):
                            lookup_key = key # use existing key w/ verified info
                            if self.gd[list_name][key]['4d_nii']: vol_dim = 4
                            widget_item = self.gd[list_name][key]['widget']
                            display_name = self.gd[list_name][key]['display_name']
        else:
            lookup_key = lookup_default
            
        if not display_name:
            display_name = lookup_key
        if not widget_item:
            widget_item = QtWidgets.QListWidgetItem(lookup_key)
            listWidget.addItem(widget_item)
            widget_item.setData(Qt.UserRole, lookup_key)
            widget_item.setText(display_name)

        self.gd[list_name][lookup_key] = {'img': img,
                                          'filepath': file_name, 
                                          'vol_ind' : int(k),
                                          '4d_nii': vol_dim > 3,
                                          'timeseries': None,
                                          'ts_filepath': None,
                                          'display_name': display_name,
                                          'lookup_name': lookup_key, 
                                          'widget': widget_item}


    def browse_ica_files(self, state=None):
        """File browser to select & load ICA files"""
        
        ts_files = []
        ica_files = None
        if os.path.exists(self.config['ica']['directory']):
            ica_dir = self.config['ica']['directory']
        else:
            ica_dir = self.config['base_directory']
            self.config['ica']['directory'] = ica_dir
        ica_files = self.browse_files(title='Select ICA Component File(s):', directory=ica_dir,
                                      filter="Image Files (*.nii.gz *.nii *.img)")
        if ica_files: #skip reset if no new ICA files are specified
            r1 = re.compile("timecourses" + self.config['ica']['search_pattern'])
            if len([f for f in filter(r1.search, ica_files)]) > 0: # mistaken selection in input         
                ts_files = [f for f in filter(r1.search, ica_files)]
                comp_files = [f.replace('timecourses',
                                        'component') for f in ts_files]
                ica_files += comp_files 
            if len(ica_files) == 1:
                ica_dir = os.path.dirname(ica_files[0])
            else:
                ica_dir = os.path.commonpath(ica_files)
                
            self.add_files_to_list(self.listWidget_ICA, 'ica', ica_files,
                                   search_pattern=self.config['ica']['search_pattern'],
                                   exclude_pattern='(timecourses|timeseries)')
            
            if (any([os.path.exists(f) for f in ts_files]) and 
                not any([os.path.exists(f) for f in comp_files])):
                    title = "Error loading Nifti volumes"
                    message = "Nifti time series file or GIFT time courses choosen/entered,"
                    message += " please select 3D or 4D nifti files"
                    QtWidgets.QMessageBox.warning(None, title, message)
            else:
                self.load_ica_timeseries(ica_files=ica_files, 
                                         search_toolbox_output=True, 
                                         prompt_fileDialog=True)
            for ica_file in ica_files:
                csv_fname = None
                if os.path.isfile(os.path.splitext(ica_file)[0] + '.csv'):
                    csv_fname = os.path.splitext(ica_file)[0] + '.csv'
                elif os.path.isfile(os.path.splitext(os.path.splitext(ica_file)[0])[0] + '.csv'):
                    csv_fname = os.path.splitext(os.path.splitext(ica_file)[0])[0] + '.csv'
                if csv_fname:
                    self.load_ic_customNames(csv_fname, list_name='ica')
            

    def load_ica_timeseries(self, ica_files=None, 
                            prompt_fileDialog=True, search_toolbox_output=True):
        """Load ICA timeseries"""
        
        if (ica_files is not None) and (len(self.gd['ica'].keys()) == 0):
            title = "Error loading IC time series"
            message = "ICA components not loaded."
            message += "\nSelect files with 'Load ICA Components'"
            message += " button or menu item"
            QtWidgets.QMessageBox.warning(None, title, message)
            return
        
        if not ica_files: ica_files = []
        ts_files = []
        ica_ts = None
        if 'ica_dir' not in locals():
            if len(ica_files) > 0:
                ica_dir = os.path.commonpath(ica_files)
            else:
                ica_dir = self.config['ica']['directory']
        
        if isinstance(ica_files, dict):
            # input format:   {'spatial map filepath' : 'time series filepath'} 
            ica_dict = ica_files
            ica_files = [f for f in ica_dict.keys() if os.path.exists(f)]
            ts_files = [f for f in ica_dict.values() if os.path.exists(f)]
            search_toolbox_output = False
            prompt_fileDialog = False
            
        elif search_toolbox_output:  
            # search for ~GIFT toolbox filenaming defaults
            r1 = re.compile("timecourses" + self.config['ica']['search_pattern'])
            r2 = re.compile('component' + self.config['ica']['search_pattern'])
            if len([f for f in filter(r1.search, ica_files)]) > 0: # if time courses in input
                ts_files = [f for f in filter(r1.search, ica_files)]
                ica_files = [f.replace('timecourses',
                                       'component') for f in ts_files]
                ica_files = [f for f in ica_files if os.path.exists(f)]
            elif len([f for f in filter(r2.search, ica_files)]) > 0: # if component sources in input
                ica_files = [f for f in filter(r2.search, ica_files)]
                ts_files = [f.replace('component',
                                      'timecourses') for f in ica_files]
                ts_files = [f for f in ts_files if os.path.exists(f)]
            
        else:
            # ordered list of filepaths to both
            r = re.compile("(time)" + self.config['ica']['search_pattern'])
            ts_files = [f for f in filter(r.search, ica_files)]
            ica_files = [f for f in ica_files if f not in ts_files]
            if len(ts_files) != len(ica_files):
                ts_files = [] # trigger dialogue input below
                
        if len(ts_files) == 0 and prompt_fileDialog:
            ica_lookups = self.gd['ica'].keys()
            ica_ts_none = [key for key in ica_lookups
                           if ((self.gd['ica'][key]['timeseries'] is None) and
                               (self.gd['ica'][key]['filepath'] is not None))]
            if len(ica_ts_none) > 0:
                ts_files = self.browse_files(title='Select ICA time series file:',
                                            directory=ica_dir, 
                                            filter='Time series saved as (*.nii.gz *.nii *.img)')
                
        if (len(ica_files) == 0) and prompt_fileDialog:
            ica_lookups = self.gd['ica'].keys()
            for key in ica_lookups:
                ica_files.append(self.gd['ica'][key]['filepath'])
            ica_files = list(set(ica_files))
            if len(ica_files) != len(ts_files):
                ica_title ='Select associated ICA component file:'
                ica_files = self.browse_files(title=ica_title,
                                directory=ica_dir, 
                                filter="Image Files (*.nii.gz *.nii *.img)")
                
        if all([ts==ic for ts,ic in zip(ts_files,ica_files)]):
            if prompt_fileDialog:
                title = "Error loading IC components & time series"
                message = "ICA component & time series files are identical:\n"
                for file in ts_files:
                    message += '\n   ' + os.path.basename(file)
                for file in ica_files:
                    message += '\n   ' + os.path.basename(file)
                QtWidgets.QMessageBox.warning(None, title, message)
            return # not able to associate ICA comp. files w/ ICA t.s. files
            
        ts_files = [f for f in ts_files if os.path.exists(f)]
        ica_files = [f for f in ica_files if os.path.exists(f)]
        if (len(ts_files) == 0) or (len(ica_files) == 0):
            if prompt_fileDialog:
                print('NOTE: could not find associated ICA timeseries')
            return
        elif len(ts_files) != len(ica_files):
            if prompt_fileDialog:
                print('ERROR: mismatch between ICA time series vs. spatial maps files')
            return
        else:
            ica_dict = dict(zip(ica_files, ts_files))
        
        # load time series & find which file is associated with which self.gd['ica'] key
        for ica_file, ts_file in ica_dict.items():
            ica_ts = image.load_img(ts_file)
            vol_dim = len(ica_ts.shape)
            if vol_dim != 2: # expect [time x ICs] vol.
                continue # skip if 3D/4D nifti vol. loaded by mistake
                # next # skip if 3D/4D nifti vol. loaded by mistake  # 6/10/2022 --kw-- next not a python keyword
            else:
                for lookup_key in self.gd['ica'].keys():
                    if ica_file == self.gd['ica'][lookup_key]['filepath']:
                        k = self.gd['ica'][lookup_key]['vol_ind']
                        if (ica_ts is not None) and (k is not None):
                            self.gd['ica'][lookup_key]['timeseries'] = ica_ts.dataobj[:,k]
                            self.gd['ica'][lookup_key]['ts_filepath'] = ts_file
            ica_ts.uncache()
            
                    
                                                    
    def browse_icn_files(self, state=None):
        """File browser & loading for ICN templates"""
        
        icn_dir = opj(self.config['base_directory'], self.config['icn']['directory'])
        icn_files = self.browse_files(title='Select ICN Template(s):', directory=icn_dir,
                                      filter="Image Files (*.nii.gz *.nii *.img)")
        if icn_files:
            if len(icn_files) == 1:
                self.config['icn']['directory'] = os.path.dirname(icn_files[0])
            else:
                self.config['icn']['directory'] = os.path.commonpath(icn_files)
            self.add_files_to_list(self.listWidget_ICN, 'icn', icn_files,
                                   search_pattern=self.config['icn']['search_pattern'],
                                   extra_items=self.config['icn']['extra_items'])
            for icn_file in icn_files:
                csv_fname = None
                if os.path.isfile(os.path.splitext(icn_file)[0] + '.csv'):
                    csv_fname = os.path.splitext(icn_file)[0] + '.csv'
                elif os.path.isfile(os.path.splitext(os.path.splitext(icn_file)[0])[0] + '.csv'):
                    csv_fname = os.path.splitext(os.path.splitext(icn_file)[0])[0] + '.csv'
                if csv_fname:
                    self.load_ic_customNames(csv_fname, list_name='icn')
            # if len(icn_files) == 1: #check if .csv table accompanies 4d nifti icn_file w/ ICN names  # 6/10/2022 --kw-- testing multiple file handling
                # if os.path.isfile(os.path.splitext(icn_files[0])[0] + '.csv'):
                #     # find_csv_labels = False   # 6/10/2022 --kw-- deprecated var.
                #     csv_fname = os.path.splitext(icn_files[0])[0] + '.csv'
                #     self.load_ic_customNames(csv_fname, list_name='icn')
                # elif os.path.isfile(os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'):
                #     # find_csv_labels = False  # 6/10/2022 --kw-- deprecated var.
                #     csv_fname = os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'
                #     self.load_ic_customNames(csv_fname, list_name='icn')
            #     else:   # 6/10/2022 --kw-- deprecated var. & fn.
            #         find_csv_labels = True
            # elif len(icn_files) > 1:
            #     find_csv_labels = True
            # else:
            #     find_csv_labels = False
                

    def load_ic_customNames(self, fname=None, list_name='icn'):
        """Load file w/ ICA or ICN names, if IC labels are different from filenames"""
        
        ic_dict = None
        fail_flag = True
        if fname:
            if not os.path.isfile(fname):
                fname = None
        else:
            f_caption = "Select saved table with IC names"
            f_caption += "\n(filenames in 1st column, new names in 2nd):"
            f_dir = '.'
            f_filter = "csv (*.csv);;Text files (*.txt)"
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, f_caption, f_dir, f_filter)
            if not os.path.isfile(fname):
                fname = None
        if fname:
            print('Re-naming '+list_name+' items using labels in file: '+fname)
            if fname.endswith('.csv'):
                with open(fname) as f:
                    names_file = list(csv.reader(f))
            elif fname.endswith('.txt'):
                with open(fname) as f:
                    names_file = f.readlines()
                names_file = [x.strip() for x in names_file]
                names_file = [x.split() for x in names_file]
            
            # Check header for required original & custom names columns:
            orig_names_col = ['Component', 'Filename', 'File', 'Template']
            new_names_col = ['Label', 'Classification']
            names_file_header = names_file[0]
            names_file_header = [colname.replace(':','') for colname in names_file_header]
            names_check0 = [colname in orig_names_col for colname in names_file_header]
            names_check1 = [colname in new_names_col for colname in names_file_header]
            if any(names_check0) and any(names_check1):
                c0 = min([i for i,x in enumerate(names_check0) if x])  # get 1st matching col. name for original names
                c1 = min([i for i,x in enumerate(names_check1) if x])  # get 1st matching col. name for new names
                content = names_file[1:]
                # content = names_file[1:][c0,c1]  # 6/13/2022 --kw-- debugging, list indexing
            else:
                return
                # content = names_file  # 6/10/2022 --kw-- deprecated, skip renaming if expected cols. not matched out of an abundance of caution
            
            ic_dict = {}
            for ic in range(len(content)):
                ic_dict.update({content[ic][c0] : content[ic][c1]})  # 6/13/2022 --kw-- note: requires 'c0' & 'c1' from above
                # ic_dict.update({content[ic][0] : content[ic][1]})  # 6/13/2022 --kw-- debugging
            fail_flag = self.replace_ic_customNames(ic_dict, list_name)
            
            if fail_flag:
                title = "Error loading saved/custom IC names"
                message = "One or more old IC labels not found in current list of IC names"
                QtWidgets.QMessageBox.warning(None, title, message)
            else:
                self.config[list_name]['labels_file'] = fname

            # 6/10/2022 --kw-- tweaking expected filenames, added ability to search for expected headers
            # # Check if 1st row is a header:
            # likely_header_names = ['ICA Component', 'ICA File', 'ICA Label',
            #                        'ICN Template', 'ICN File', 'ICN Label', 
            #                        'Noise Classification']
            # names_file0 = names_file[0]
            # names_file0 = [colname.replace(':','') for colname in names_file0]
            # if any([colname in likely_header_names for colname in names_file0]):
            #     header, content = names_file[0], names_file[1:]
            # else:
            #     content = names_file
#             
#             # 1st col. is existing IC name (~file name), 2nd col. is new/customized IC name
#             ic_dict = {}
#             for ic in range(len(content)):
#                 ic_dict.update({content[ic][0] : content[ic][1]})
#             fail_flag = self.replace_ic_customNames(ic_dict, list_name)
            
#             if fail_flag:
#                 title = "Error loading saved/custom IC names"
#                 message = "One or more old IC labels not found in current list of IC names"
#                 QtWidgets.QMessageBox.warning(None, title, message)
#             else:
#                 self.config[list_name]['labels_file'] = fname
                

    def replace_ic_customNames(self, ic_dict, list_name='icn', listWidget=None):
        """Replace IC template names w/ names from csv table"""
        
        fail_flag = False
        if not listWidget:
            if not list_name:
                return True
            elif list_name == 'icn':
                listWidget = self.listWidget_ICN
            elif list_name == 'ica':
                listWidget = self.listWidget_ICA
            else:
                return True
        
        lookup_names_list = self.get_item_prop(list_name, 'lookup_name')
        file_names_list = self.get_item_prop(list_name, 'filepath')
        vol_inds_list = self.get_item_prop(list_name, 'vol_ind')
        vol_inds_list = [str(ind) for ind in vol_inds_list]
        
        keys1_lookups, keys1_files, keys1_inds = False, False, False
        test_keys1_lookups = []        
        test_keys1_files = []
        test_keys1_inds = []
        ic_dict_keys1 = [*ic_dict]
        for key in ic_dict_keys1:
            test_keys1_lookups.append(key in lookup_names_list)
            test_keys1_files.append(key in file_names_list)
            test_keys1_inds.append(key in vol_inds_list)
        if any(test_keys1_lookups): keys1_lookups = True
        if any(test_keys1_files): keys1_files = True
        if any(test_keys1_inds): keys1_inds = True
        for k,key in enumerate(ic_dict_keys1):
            if not any([test_keys1_lookups[k], test_keys1_files[k], test_keys1_inds[k]]):
                ic_dict_keys1.remove(key)
                ic_dict.pop(key, None) #None avoids error if key not in dict
                        
        keys2_lookups, keys2_files, keys2_inds = False, False, False
        if isinstance(ic_dict[ic_dict_keys1[0]], dict):
            for key1 in ic_dict_keys1:
                test_keys2_lookups = []
                test_keys2_files = []
                test_keys2_inds = []
                ic_dict_keys2 = [*ic_dict[key1]]
                for key2 in ic_dict_keys2:
                    test_keys2_lookups.append(key2 in lookup_names_list)
                    test_keys2_files.append(key2 in file_names_list)
                    test_keys2_inds.append(key2 in vol_inds_list)
                if any(test_keys2_lookups): keys2_lookups = True
                if any(test_keys2_files): keys2_files = True
                if any(test_keys2_inds): keys2_inds = True
                for k,key2 in enumerate(ic_dict_keys2):
                    if not any([test_keys2_lookups[k], test_keys2_files[k], test_keys2_inds[k]]):
                        ic_dict_keys2.remove(key2)
                if len(ic_dict_keys2) == 0:
                    ic_dict_keys1.remove(key1)
                    ic_dict.pop(key1, None) #None avoids error if key not in dict
                    
        ic_dict_replace = {}
        K = len(lookup_names_list)
        for key1,replacement1 in ic_dict.items():
            k1, old_name, new_name = [], None, None
            if isinstance(replacement1, str):
                new_name = replacement1
            if keys1_lookups and (key1 in lookup_names_list):
                k1 = [k for k in range(K) if (key1 == lookup_names_list[k])]
            elif keys1_files and (key1 in file_names_list):
                k1 = [k for k in range(K) if (key1 == file_names_list[k])]
            elif keys1_inds and (key1 in vol_inds_list):
                k1 = [k for k in range(K) if (key1 == vol_inds_list[k])]
            if len(k1) == 1:
                old_name = lookup_names_list[k1[0]]
            if old_name and new_name and (old_name != new_name):
                ic_dict_replace.update({old_name : new_name})
            else:
                if not any([keys2_lookups, keys2_files, keys2_inds]):
                    fail_flag = True
                    continue
                for key2,replacement2 in ic_dict[key1].items():
                    k2, old_name, new_name = [], None, None
                    if isinstance(replacement2, str):
                        new_name = replacement2
                    if keys2_lookups and (key2 in lookup_names_list):
                        k2 = [k for k in range(K) if (key2 == lookup_names_list[k])]
                    elif keys2_files and (key2 in file_names_list):
                        k2 = [k for k in range(K) if (key2 == file_names_list[k])]
                    elif keys2_inds and (key2 in vol_inds_list):
                        k2 = [k for k in range(K) if (key2 == vol_inds_list[k])]
                    if len(set(k1) & set(k2)) == 1:
                        old_name = lookup_names_list[list(set(k1) & set(k2))[0]]
                    if old_name and new_name and (old_name != new_name):
                        ic_dict_replace.update({old_name : new_name})
                    else:
                        fail_flag = True
                        
        for old_name, new_name in ic_dict_replace.items():
            if old_name and new_name and (old_name != new_name):
                old_item = listWidget.findItems(old_name, Qt.MatchExactly)
                if (old_item is None) or (len(old_item) == 0):
                    fail_flag = True
                else:
                    if len(listWidget.findItems(new_name, Qt.MatchExactly)) > 0:
                        #  replace templates w/ duplicate names
                        outdated_item = listWidget.findItems(new_name, Qt.MatchExactly)
                        listWidget.takeItem(listWidget.row(outdated_item[0]))
                    listWidget.takeItem(listWidget.row(old_item[0]))
                    new_item = QtWidgets.QListWidgetItem(new_name)
                    listWidget.addItem(new_item)
                    new_item.setData(Qt.UserRole, new_name)
                    new_item.setText(new_name)
                    self.gd[list_name][new_name] = self.gd[list_name].pop(old_name)
                    self.gd[list_name][new_name]['display_name'] = new_name
                    self.gd[list_name][new_name]['lookup_name'] = new_name
                    self.gd[list_name][new_name]['widget'] = new_item
        
        return fail_flag
        
    
    def expand_ROI_atlas_vol(self, roi_files=None, roi_dict=None,
                             list_name='icn', listWidget=None):
        """Decompresses/rearranges list item for a single atlas vol., 
        with ROIs indexed as integers, into separate list items"""

        if roi_files is None and roi_dict is None: return
        if listWidget is None:
            if not list_name:
                roi_dict = None
            elif list_name == 'icn':
                listWidget = self.listWidget_ICN
            elif list_name == 'ica':
                listWidget = self.listWidget_ICA
            else:
                roi_dict = None
        if isinstance(roi_files, str):
            roi_files = [roi_files]
        
        outdated_lookup_keys = []
        if isinstance(roi_files, (list, tuple)):
            for file in roi_files:
                for key in self.gd[list_name].keys():
                    if file == self.gd[list_name][key]['filepath']:
                        outdated_lookup_keys.append(key)
        if roi_dict:
            for key in roi_dict.keys():
                if key in self.gd[list_name].keys():
                    outdated_lookup_keys.append(key)
        else:
            roi_dict = {}
            
        outdated_lookup_keys = list(set(outdated_lookup_keys)) #rm. duplicates
        for outdated_lookup in outdated_lookup_keys:
            outdated_item = self.gd[list_name][outdated_lookup]['widget']
            outdated_img = self.gd[list_name][outdated_lookup]['img']
            vol_filename = self.gd[list_name][outdated_lookup]['filepath']
            vol_dim = len(outdated_img.shape)
            roi_array = outdated_img.get_fdata(caching='unchanged')
            roi_inds = np.unique(roi_array).tolist()
            if 0 in roi_inds: roi_inds.remove(0)
            listWidget.takeItem(listWidget.row(outdated_item))
            self.gd[list_name].pop(outdated_lookup)
            
            for ind in roi_inds:                    
                roi_img = image.new_img_like(outdated_img, roi_array==ind, copy_header=True)
                roi_lookup = outdated_lookup + ',' + str(int(float(ind)))
                if str(int(float(ind))) in roi_dict.keys():
                    roi_label = roi_dict.pop(str(ind))
                else:
                    roi_label = roi_lookup
                roi_dict.update({roi_lookup: roi_label})
                item = QtWidgets.QListWidgetItem(roi_lookup)
                listWidget.addItem(item)
                item.setData(Qt.UserRole, roi_lookup)
                item.setText(roi_lookup)
                self.gd[list_name][roi_lookup] = {'img': roi_img,
                                                  'filepath': vol_filename,
                                                  'vol_ind' : ind,
                                                  '4d_nii': vol_dim > 3,
                                                  'timeseries': None,
                                                  'ts_filepath': None,
                                                  'lookup_name': roi_lookup,
                                                  'display_name': roi_lookup,
                                                  'widget': item}
        return(roi_dict)
            
    
    def save_analysis_json(self, fname):
        """Save info needed for analysis (but not loaded ICA/ICN volumes), for 'load_analysis()' fn."""
            
        config = self.config
        ica_files = [self.gd['ica'][lookup_key]['filepath'] for lookup_key in self.gd['ica'].keys()]
        ica_files = list(set(ica_files))
        ica_files = [f for f in ica_files if f is not None]
        ts_files = [self.gd['ica'][lookup_key]['ts_filepath'] for lookup_key in self.gd['ica'].keys()]
        ica_ts_files = dict(zip(ica_files, ts_files))
        ica_IndstoNames = {}
        for file in ica_files: #create key for each unique file
            ica_IndstoNames[file] = {}
        for lookup_key in self.gd['ica'].keys():
            file = self.gd['ica'][lookup_key]['filepath']
            ica_IndstoNames[file].update([(self.gd['ica'][lookup_key]['vol_ind'], lookup_key)])
        ica_customNames = {lookup_key : self.gd['ica'][lookup_key]['display_name'] for lookup_key in self.gd['ica'].keys()}  # 6/8/2022 --kw-- adding save & loading for custom ICA names
        icn_files = [self.gd['icn'][lookup_key]['filepath'] for lookup_key in self.gd['icn'].keys()]
        icn_files = list(set(icn_files))
        icn_files = [f for f in icn_files if f is not None]
        icn_IndstoNames = {}
        for file in list(set(icn_files)): #create key for each unique file
            icn_IndstoNames[file] = {}
        for lookup_key in self.gd['icn'].keys():
            file = self.gd['icn'][lookup_key]['filepath']
            if file is not None:
                icn_IndstoNames[file].update([(self.gd['icn'][lookup_key]['vol_ind'], lookup_key)])        
        icn_customNames = {lookup_key : self.gd['icn'][lookup_key]['display_name'] for lookup_key in self.gd['icn'].keys()}  # 6/8/2022 --kw-- adding save & loading for custom ICN names
        
        corrs = self.corrs
        
        ica_icn_mapped = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_lookup'] for mapping_key in self.gd['mapped'].keys()}
        ica_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['ica_custom_name'] for mapping_key in self.gd['mapped'].keys()}
        icn_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_custom_name'] for mapping_key in self.gd['mapped'].keys()}
        
        analysisInfo = {'info' : 'Saved analysis file, created by Network Zoo',
                        'config' : config, 
                        'ica_files' : ica_files, 
                        'ica_ts_files' : ica_ts_files,
                        'ica_IndstoNames' : ica_IndstoNames, 
                        'ica_customNames' : ica_customNames,  # 6/8/2022 --kw-- added save & load custom names feature
                        'icn_files' : icn_files,
                        'icn_IndstoNames' : icn_IndstoNames, 
                        'icn_customNames' : icn_customNames,  # 6/8/2022 --kw-- added save & load custom names feature
                        'corrs' : corrs, 
                        'ica_icn_mapped' :ica_icn_mapped, 
                        'ica_mapped_customNames' : ica_mapped_customNames, 
                        'icn_mapped_customNames' : icn_mapped_customNames}
        
        with open(fname, 'w') as f:
            json.dump(analysisInfo, f)
                

    def load_analysis_json(self, fname):
        """Load info from file created by 'save_analysis()' fn."""
        
        with open(fname, 'rb') as f:
            analysisInfo = json.load(f)
            
        load_analysis_error = False
        title = "Error loading analysis"
        if 'info' not in analysisInfo.keys():
            load_analysis_error = True
            message = "Selected file does not appear to contain saved Network Zoo analysis"
        elif analysisInfo['info']  != 'Saved analysis file, created by Network Zoo':
            load_analysis_error = True
            message = "Selected file does not appear to contain saved Network Zoo analysis"
        elif not set(['config','ica_files','ica_IndstoNames', 'ica_ts_files',
                      'icn_files','icn_IndstoNames','corrs','ica_icn_mapped',
                      'ica_mapped_customNames','icn_mapped_customNames']) <= set(analysisInfo.keys()):
            load_analysis_error = True
            message = "Selected file does not appear to contain saved Network Zoo analysis"
        
        if load_analysis_error:
            QtWidgets.QMessageBox.warning(None, title, message)
            return
        else:
            config                 = analysisInfo['config'] # software defaults & configuration info
            ica_files              = analysisInfo['ica_files'] # ICA file paths
            ica_IndstoNames        = analysisInfo['ica_IndstoNames'] # 4d nii indices for above files
            ica_ts_files           = analysisInfo['ica_ts_files']  # file paths to time series
            ica_customNames        = analysisInfo['ica_customNames'] # custom display names   # 6/8/2022 --kw-- adding save/load customnames features
            icn_files              = analysisInfo['icn_files'] # ICN template file paths
            icn_IndstoNames        = analysisInfo['icn_IndstoNames'] # 4d nii indices for above files
            icn_customNames        = analysisInfo['icn_customNames'] # custom display names   # 6/8/2022 --kw-- adding save/load customnames features
            corrs                  = analysisInfo['corrs'] # dict of correlations, indexed as IC : ICN
            ica_icn_mapped         = analysisInfo['ica_icn_mapped'] # dict of ICA > ICN mappings
            ica_mapped_customNames = analysisInfo['ica_mapped_customNames'] # custom ICA names for above
            icn_mapped_customNames = analysisInfo['icn_mapped_customNames'] # custom ICN names for above
            
            # Sanity checks
            message = ""
            if not all([os.path.exists(f) for f in ica_files]):
                load_analysis_error = True
                message += "\n\nSaved ICA file(s) appear to be missing!"
                missing_files = [f for f in ica_files if not os.path.exists(f)]
                ica_files = [f for f in ica_files if f not in missing_files]
                if len(ica_files) > 0:
                    message += " Could not find:"
                    for f in missing_files:
                        message += "\n"+f
                else:
                    message += " Could not find: "+ opj(os.path.commonpath(missing_files), "*")
                
            if not all([os.path.exists(f) for f in icn_files]):
                load_analysis_error = True
                message += "\n\nSaved ICN template file(s) appear to be missing!"
                missing_files = [f for f in icn_files if not os.path.exists(f)]
                icn_files = [f for f in icn_files if f not in missing_files]
                if len(icn_files) > 0:
                    message += " Could not find:"
                    for f in missing_files:
                        message += "\n"+f
                else:
                    message += " Could not find: "+ opj(os.path.commonpath(missing_files), "*")
            if load_analysis_error:
                if (len(ica_files)==0) and (len(icn_files)==0):
                    message += "Unable to load saved analysis"
                    QtWidgets.QMessageBox.warning(None, title, message)
                    return
                else:
                    message += "\n\nExcluding above & attempting to load existing files..."
                    QtWidgets.QMessageBox.warning(None, title, message)
                    
            self.config = InputHandling.config_check_defaults(config)
            self.add_files_to_list(self.listWidget_ICA, 'ica', 
                                   ica_files, file_inds=ica_IndstoNames,
                                   search_pattern=self.config['ica']['search_pattern'], 
                                   append=False)
            if ica_ts_files is not None:
                self.load_ica_timeseries(ica_files=ica_ts_files, 
                                         prompt_fileDialog=False, 
                                         search_toolbox_output=False)
            if ica_customNames is not None:     # 6/8/2022 --kw-- new feature, save/load custom display names
                for ica_lookup in ica_customNames.keys():
                    self.gd['ica'][ica_lookup]['display_name'] = ica_customNames[ica_lookup]
            
            extra_template_items = self.config['icn']['extra_items'].copy()
            extra_template_items += self.config['noise']['extra_items'].copy()
            self.add_files_to_list(self.listWidget_ICN, 'icn', 
                                   icn_files, file_inds=icn_IndstoNames,
                                   search_pattern=self.config['icn']['search_pattern'],
                                   extra_items=extra_template_items,
                                   append=False)
            if icn_customNames is not None:                          # 6/8/2022 --kw-- new feature, save/load custom display names
                for icn_lookup in icn_customNames.keys():
                    self.gd['icn'][icn_lookup]['display_name'] = icn_customNames[icn_lookup]

            if corrs is not None:
                self.corrs = corrs
                
            for ica_lookup, icn_lookup in ica_icn_mapped.items():
                self.add_saved_Classification(ica_icn_pair=(ica_lookup, icn_lookup),
                                              ica_custom_name=ica_mapped_customNames[ica_lookup],
                                              icn_custom_name=icn_mapped_customNames[ica_lookup])
                
            
    def add_saved_Classification(self, ica_icn_pair=None, ica_custom_name=None, 
                                 icn_custom_name=None, updateGUI=True):
        """Add ICA > ICN mapping to Qt list, customized for 'load_analysis_json()'"""
        
        if len(ica_icn_pair) == 2:
            ica_lookup, icn_lookup = ica_icn_pair
        elif (ica_icn_pair is None) or (ica_icn_pair is False):
            return
        else:
            return
        if ica_lookup not in self.gd['ica'].keys(): return
        if icn_lookup not in self.gd['icn'].keys(): return
        
        if ica_custom_name is None: ica_custom_name = ica_lookup
        if icn_custom_name is None: icn_custom_name = icn_lookup
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
            self.listWidget_mapped.addItem(map_itemWidget)
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            
            # # Remove ICA item from ICA listwidget (but not in gd['ica'])  # 6/13/2022 --kw-- moved to below
            # if not self.config['ica']['allow_multiclassifications']:
            #     ica_items = self.listWidget_ICA.findItems(ica_lookup, Qt.MatchExactly)
            #     for ica_item in ica_items:
            #         self.listWidget_ICA.takeItem(self.listWidget_ICA.row(ica_item))

        elif icn_lookup: 
            # Create new empty mapping to ICN mask, for visualization purposes
            map_itemWidget = QtWidgets.QListWidgetItem(mapping_lookup)
            self.listWidget_mapped.addItem(map_itemWidget)
            map_itemWidget.setData(Qt.UserRole, mapping_lookup)
            
        else:
            return #nothing selected, nothing to do
        
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
        
        # Remove ICA item from ICA listwidget (but not in gd['ica'])
        if ica_lookup and not self.config['ica']['allow_multiclassifications']:
            ica_display_name = self.gd['ica'][ica_lookup]['display_name']
            ica_items = self.listWidget_ICA.findItems(ica_display_name, Qt.MatchExactly)
            # ica_items = self.listWidget_ICA.findItems(ica_lookup, Qt.MatchExactly)  # 6/13/2022 --kw-- deprecated
            for ica_item in ica_items:
                self.listWidget_ICA.takeItem(self.listWidget_ICA.row(ica_item))
            self.gd['ica'][ica_lookup]['widget'] = None


    @staticmethod
    def replace_faulty_config(config_file, mypath=None, config_backup=None):
        """Delete faulty config file, replace w/ backup config file"""
        
        if config_backup is None:
            if mypath is None:
                if ('__file__' in locals()) or ('__file__' in globals()):
                    mypath = os.path.dirname(os.path.abspath(__file__)) 
                else:
                    mypath = os.getcwd()
            backup_default = opj(mypath, 'config_settings', 'config_settings_backup.py')
            if os.path.isfile(backup_default):
                # load default backup configuration settings, saved as .py file
                from config_settings_backup import default_configuration as config_backup
            else:
                message = "Found faulty configuration file:  '" + fname + "'"
                message += "\nAdditionally, could not find default "
                message += "configuration background settings file: "
                message += "'" + backup_default + "'"
                message += "\n\nIf problems persist, recommend re-installing program"
                QtWidgets.QMessageBox.warning(None, title, message)
        config = config_backup
        
        if os.path.isfile(config_file):
            os.remove(config_file)                                                                     
        with open(config_file, 'w') as json_file:
            json.dump(config, json_file)
            
        return config

                
    @staticmethod
    def config_check_defaults(configData, mypath=None, config_backup=None):
        """Check configuration for required fields, 
        set defaults if missing, return config """
        
        if mypath is None:
            if 'base_directory' in configData.keys():
                if configData['base_directory']:
                    if os.path.isdir(configData['base_directory']):
                        mypath = configData['base_directory']
        if mypath is None:
            if ('__file__' in locals()) or ('__file__' in globals()):
                mypath = os.path.dirname(os.path.abspath(__file__)) 
            else:
                mypath = os.getcwd()
                
        if config_backup is None:
            backup_default = opj(mypath, 'config_settings', 'config_settings_backup.py')
            if os.path.isfile(backup_default):
                # default backup configuration settings
                from config_settings_backup import default_configuration as config_backup
            else:
                message = "WARNING: could not find default configuration background settings file: "
                message += "'" + backup_default + "', "
                message += "display options & editing preferrence may be buggy!"
                print(message)

        # Check for defaults
        if 'base_directory' not in configData.keys(): 
            configData['base_directory'] = mypath
        elif configData['base_directory'] is None:
            configData['base_directory'] = mypath
        elif not os.path.isdir(configData['base_directory']):
            configData['base_directory'] = mypath
        if 'output_directory' not in configData.keys():
            configData['output_directory'] = configData['base_directory']
        else:
            configData['output_directory'] = opj(configData['base_directory'], 
                                                 configData['output_directory'])
        if 'corr_onClick' not in configData.keys(): configData['corr_onClick'] = True
        if 'saved_analysis' not in configData.keys(): configData['saved_analysis'] = False
        if 'saved_analysis_path' not in configData.keys(): configData['saved_analysis_path'] = ""
        if 'output_created' not in configData.keys(): configData['output_created'] = False

        # Load display settings
        warning_flag = False
        if 'display' not in configData.keys():
            configData['display'] = {}
        if 'mri_plots' not in configData['display']:
            configData['display']['mri_plots'] = config_backup['display']['mri_plots']
            warning_flag = True
        if 'time_plots' not in configData['display']:
            configData['display']['time_plots'] = config_backup['display']['time_plots']
            warning_flag = True
        if warning_flag:
            title = "Error configuring networkZoo"
            message = "Could not find required plotting fields in configuration file!"
            message += " Defaulting to backup settings"
            QtWidgets.QMessageBox.warning(None, title, message)

        # Prepend script dir. to paths
        script_path = configData['base_directory']
        
        if os.path.exists(opj(script_path, configData['ica']['directory'])):
            configData['ica']['directory'] = opj(script_path, configData['ica']['directory'])
        if os.path.isfile(configData['ica']['directory']):
            configData['ica']['directory'] = os.path.dirname(configData['ica']['directory'])
            
        if os.path.exists(opj(script_path, configData['icn']['directory'])):
            configData['icn']['directory'] = opj(script_path, configData['icn']['directory'])
        if os.path.isfile(configData['icn']['directory']):
            configData['icn']['directory'] = os.path.dirname(configData['icn']['directory'])
            
        if os.path.exists(opj(script_path, configData['noise']['directory'])):
            configData['noise']['directory'] = opj(script_path, configData['noise']['directory'])
        if os.path.isfile(configData['noise']['directory']):
            configData['noise']['directory'] = os.path.dirname(configData['noise']['directory'])
            
        if os.path.isfile(opj(script_path, configData['smri_file'])):
            configData['smri_file'] = opj(script_path, configData['smri_file'])
        
        return configData

