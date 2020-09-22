# Python Libraries
from os.path import join as opj  # method to join strings of file paths
import os, sys, re, json, csv

# Qt GUI Libraries
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt


# Mathematical/Neuroimaging/Plotting Libraries
import numpy as np
from nilearn import plotting, image, input_data  # library for neuroimaging
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
        
        
        
    def configure_ICs(self):
        """Load anatomical file, ICA comps, ICN & noise templates on startup"""
        
        if os.path.isfile(self.config['smri_file']):
            self.load_single_file(self.config['smri_file'], file_type='smri')
        if os.path.exists(self.config['ica']['directory']):
            ica_files = self.find_files(self.config['ica']['directory'], 
                                        self.config['ica']['template'],
                                        self.config['ica']['search_pattern'],
                                        list_name='ica')
            self.load_ica_timeseries(ica_files, prompt_fileDialog=False)
        if os.path.exists(self.config['icn']['directory']):
            self.find_files(self.config['icn']['directory'], 
                            self.config['icn']['template'], 
                            self.config['icn']['search_pattern'],
                            list_name='icn', 
                            extra_items=self.config['icn']['extra_items'])
        if os.path.exists(self.config['noise']['directory']):
            self.find_files(self.config['noise']['directory'], 
                            self.config['noise']['template'], 
                            self.config['noise']['search_pattern'],
                            list_name='icn', 
                            extra_items=self.config['noise']['extra_items'])


    def load_noise_templates(self):
        """Load noise templates"""
        
        for extra in self.config['noise']['extra_items']: #temporarily remove nontemplate slot from list
                item = self.listWidget_ICN.findItems(extra, Qt.MatchExactly)
                if len(item) > 0:
                    self.listWidget_ICN.takeItem(self.listWidget_ICN.row(item[0]))
        os.chdir(self.config['base_directory'])
        self.find_files(self.config['noise']['directory'], 
                        self.config['noise']['template'], 
                        self.config['noise']['search_pattern'], 
                        list_name='icn', 
                        extra_items=self.config['noise']['extra_items'])  

    def load_demo_files(self, demo_ica_path):
        """Demo ICA run from Smith et al. 2009 (w/o timeseries)"""
        
        ica_files = self.find_files(os.path.dirname(demo_ica_path), 
                                    self.config['ica']['template'], self.config['ica']['search_pattern'],
                                    list_name='ica')
        self.load_ica_timeseries(ica_files, prompt_fileDialog=False)

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
                all_nifti_files = [directory]
            else:
                ds = nio.DataGrabber(base_directory=directory, template=template, sort_filelist=True)
                all_nifti_files = ds.run().outputs.outfiles
                
            self.add_files_to_list(listWidget, list_name, 
                                   all_nifti_files, None, 
                                   search_pattern, exclude_pattern, extra_items)

            # Load replacement IC labels stored in csv file, if applicable
            if os.path.splitext(all_nifti_files[0])[-1] in ['.img', '.hdr', '.nii']:
                csv_fname = os.path.splitext(all_nifti_files[0])[0] + '.csv'
            elif os.path.splitext(all_nifti_files[0])[-1] not in ['.nii.gz']:
                csv_fname = os.path.splitext(all_nifti_files[0])[0]
                csv_fname = os.path.splitext(csv_fname)[0] + '.csv'
            if os.path.isfile(csv_fname):
                self.load_ic_customNames(csv_fname, list_name)
                
            return(all_nifti_files)
        
    
    def add_files_to_list(self, listWidget, list_name, files_to_add, file_inds=None, 
                          search_pattern='*', exclude_pattern=None, extra_items=None, append=True):
        """Add files to list & format info for parsing w/ networkZoo"""
        
        if not append: # Used when loading saved analyses
            listWidget.clear() # ...in case there are any existing elements in the list
            self.gd[list_name] = {}
        files_to_add = [f for f in files_to_add if f is not None]
        
        if len(files_to_add) > 1:
            files_to_add = list(set(files_to_add))  #remove duplicate entires for ICNs stored as 4D nifti files
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
                if vol_dim < 3: #if 2D nifti choosen by mistake...
                    title = "Error loading Nifti volumes"
                    message = "2D nifti file or GIFT time series file choosen/entered,"
                    message += " please select 3D or 4D nifti files"
                    QtWidgets.QMessageBox.warning(None, title, message)
                elif file_inds: #index individual vols w/n 4d vol., or 3d vol. indexed by intensities
                    k_range = [int(k) for k in file_inds[file_name].keys()]
                elif vol_dim == 3:
                    k_range = range(1)
                else:
                    k_dim = img_vol.shape[3]
                    k_range = range(k_dim)
                if vol_dim > 3: # iter_img() preferred over index_img() for repeated img indexing
                    for k, img in enumerate(image.iter_img(img_vol)):
                        if k not in k_range: continue
                            
                        if file_inds:
                            lookup_key = file_inds[file_name][str(k)]
                        else:
                            lookup_key = file_name
                            if search_pattern is not None:
                                match = re.search(r_pattern, lookup_key)
                                if match: lookup_key = match.groups()[0]
                            if len(k_range) > 1:
                                lookup_key = lookup_key + ',%d' %(int(k)+1)

                        item = QtWidgets.QListWidgetItem(lookup_key)
                        listWidget.addItem(item)
                        item.setData(Qt.UserRole, lookup_key)
                        item.setText(lookup_key)

                        self.gd[list_name][lookup_key] = {'img': img, 
                                                          'filepath': file_name, 
                                                          'vol_ind' : int(k),
                                                          '4d_nii': vol_dim > 3,
                                                          'timeseries': None,
                                                          'display_name': lookup_key,
                                                          'lookup_name': lookup_key, 
                                                          'widget': item}
                        
                elif vol_dim ==3: # iter_img() not applicable to non-4D volumes
                    k, img = 0, img_vol
                    if file_inds:
                        lookup_key = file_inds[file_name][str(k)]
                    else:
                        lookup_key = file_name
                        if search_pattern is not None:
                            match = re.search(r_pattern, lookup_key)
                            if match: lookup_key = match.groups()[0]
                        if len(k_range) > 1:
                            lookup_key = lookup_key + ',%d' %(int(k)+1)

                    item = QtWidgets.QListWidgetItem(lookup_key)
                    listWidget.addItem(item)
                    item.setData(Qt.UserRole, lookup_key)
                    item.setText(lookup_key)

                    self.gd[list_name][lookup_key] = {'img': img,
                                                      'filepath': file_name, 
                                                      'vol_ind' : int(k),
                                                      '4d_nii': vol_dim > 3,
                                                      'timeseries': None,
                                                      'display_name': lookup_key,
                                                      'lookup_name': lookup_key, 
                                                      'widget': item}
                    
                    # if all intensities in img are integers w/ few unique values...
                    v_unique = np.unique(img.get_fdata())
                    if (file_inds is None) and ((np.mod(v_unique,1) == 0).all()
                                                and (3 < len(v_unique) < 1000)):
                        # ...expand contents of ROI atlas as separate list items
                        self.expand_ROI_atlas_vol(file_name, list_name=list_name, listWidget=listWidget)
                        
                if file_inds: # replace default names, if provided
                    if k not in k_range: # if 4d vol. indexed by k, last index may not be included...
                        k = len(file_inds[file_name])-1 #...set k to index last value in file_inds for below
                    
                    if (len(file_inds[file_name]) > 1) | ([*file_inds[file_name].values()][k] != lookup_key):
                        self.replace_ic_customNames(file_inds[file_name], list_name, listWidget)
                        
        if extra_items:
            for extra in extra_items:
                if extra not in self.gd[list_name].keys():
                    item = QtWidgets.QListWidgetItem(extra)
                    listWidget.addItem(item)
                    item.setData(Qt.UserRole, extra)
                    item.setText(extra)
                    self.gd[list_name][extra] = {'img': None, 
                                                 'filepath': None, 
                                                 'vol_ind' : 0,
                                                 '4d_nii': False,
                                                 'timeseries': None,
                                                 'display_name': extra, 
                                                 'lookup_name': extra,
                                                 'widget': item}
        listWidget.clearSelection()  # does not change current item, but paradoxically deselects it
        listWidget.setCurrentRow(-1) # deselect everything

        
    def browse_ica_files(self, state=None):
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
            self.add_files_to_list(self.listWidget_ICA, 'ica', ica_files,
                                   search_pattern=self.config['ica']['search_pattern'],
                                   exclude_pattern='(timecourses|timeseries)')
            self.load_ica_timeseries(ica_files)
            

    def load_ica_timeseries(self, ica_files, k=None, lookup_key=None, prompt_fileDialog=True):
        """Load ICA timeseries"""
        
        ica_ts = None
        r = re.compile("(timecourses|timeseries)" + self.config['ica']['search_pattern'])
        if len([f for f in filter(r.search, ica_files)]) is 1: #first, try to find time courses in ica filelist...
            ts_file = [f for f in filter(r.search, ica_files)]  
        elif len([f for f in filter(r.search, [ica_files[0].replace('mean_component', 'mean_timecourses')])]) is 1:
            ts_file = [f for f in filter(r.search, [ica_files[0].replace('mean_component', 'mean_timecourses')])]
        else:
            ts_file = []
            if prompt_fileDialog:
                if QtWidgets.QMessageBox.question(None, '', "Are ICA time courses saved in a separate file?",
                                                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                                  QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.Yes:
                    if 'ica_dir' not in locals():
                        ica_dir = os.path.commonpath(ica_files)
                    ts_file = self.browse_files(title='Select ICA time series file:',
                                                directory=ica_dir, 
                                                filter='Time series saved as (*.nii.gz *.nii *.img)')
        if len(ts_file) == 0:
            ts_file = None
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
                
        if k and lookup_key in self.gd['ica'].keys(): #specify index by k & ica lookup key
            if ica_ts is not None:
                self.gd['ica'][lookup_key]['timeseries'] = ica_ts[:,k]
            else:
                self.gd['ica'][lookup_key]['timeseries'] = None
        else:  # find which file is associated with which self.gd['ica'] key
            for file in ica_files:
                for lookup_key in self.gd['ica'].keys():
                    if file == self.gd['ica'][lookup_key]['filepath']:
                        k = re.findall(r'\d+$', lookup_key) #get last digit in IC comp. name
                        k = int(k[0]) if len(k) > 0 else None
                        if ica_ts is not None and k is not None:
                            self.gd['ica'][lookup_key]['timeseries'] = ica_ts[:,k-1]
                    
                                                    
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
            
            if len(icn_files) == 1:     #check if .csv table accompanies 4d nifti icn_file w/ ICN names
                if os.path.isfile(os.path.splitext(icn_files[0])[0] + '.csv'):
                    find_csv_labels = False
                    csv_fname = os.path.splitext(icn_files[0])[0] + '.csv'
                    self.load_ic_customNames(csv_fname, list_name='icn')
                elif os.path.isfile(os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'):
                    find_csv_labels = False
                    csv_fname = os.path.splitext(os.path.splitext(icn_files[0])[0])[0] + '.csv'
                    self.load_ic_customNames(csv_fname, list_name='icn')
                else:
                    find_csv_labels = True
            elif len(icn_files) > 1:
                find_csv_labels = True
            else:
                find_csv_labels = False
                

    def load_ic_customNames(self, fname=None, list_name='icn'):
        """Load file w/ ICA or ICN names, if IC labels are different from filenames"""
        
        ic_dict = None
        fail_flag = True
        if fname:
            if not os.path.isfile(fname):
                fname = None
        else:
            f_caption = "Select saved table with IC names"
            f_caption = f_caption + "\n(filenames in 1st column, new names in 2nd):"
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
            
            # Check if 1st row is a header:
            likely_header_names = ['ICA Component', 'ICA File', 'ICA Label',
                                   'ICN Template', 'ICN File', 'ICN Label', 
                                   'Noise Classification']
            names_file0 = names_file[0]
            names_file0 = [colname.replace(':','') for colname in names_file0]
            if any(colname in likely_header_names for colname in names_file0):
                header, content = names_file[0], names_file[1:]
            else:
                content = names_file
            
            # 1st col. is existing IC name (~file name), 2nd col. is new/customized IC name
            ic_dict = {}
            for ic in range(len(content)):
                ic_dict.update({content[ic][0] : content[ic][1]})
                
            fail_flag = self.replace_ic_customNames(ic_dict, list_name)
            
            if fail_flag:
                title = "Error loading saved/custom IC names"
                message = "One or more old IC labels not found in current list of IC names"
                QtWidgets.QMessageBox.warning(None, title, message)
            else:
                self.config[list_name]['labels_file'] = fname
                

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
            
        for old_name, new_name in ic_dict.items():
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
            roi_array = outdated_img.get_fdata()
            roi_inds = np.unique(roi_array).tolist()
            if 0 in roi_inds: roi_inds.remove(0)
            listWidget.takeItem(listWidget.row(outdated_item))
            self.gd[list_name].pop(outdated_lookup)
            for ind in roi_inds:                    
                roi_img = image.new_img_like(outdated_img, roi_array==ind, copy_header=True)
                roi_lookup = outdated_lookup + ',' + str(int(ind))
                if str(int(ind)) in roi_dict.keys():
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
        ica_IndstoNames = {}
        for file in ica_files: #create key for each unique file
            ica_IndstoNames[file] = {}
        for lookup_key in self.gd['ica'].keys():
            file = self.gd['ica'][lookup_key]['filepath']
            ica_IndstoNames[file].update([(self.gd['ica'][lookup_key]['vol_ind'], lookup_key)])
            ica_ts = {lookup_key : self.gd['ica'][lookup_key]['timeseries'].tolist()
                      for lookup_key in self.gd['ica'].keys()}

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
                
        corrs = self.corrs
        
        ica_icn_mapped = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_lookup'] for mapping_key in self.gd['mapped'].keys()}
        ica_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['ica_custom_name'] for mapping_key in self.gd['mapped'].keys()}
        icn_mapped_customNames = {self.gd['mapped'][mapping_key]['ica_lookup'] : self.gd['mapped'][mapping_key]['icn_custom_name'] for mapping_key in self.gd['mapped'].keys()}
        
        analysisInfo = {'info' : 'Saved analysis file, created by Network Zoo',
                        'config' : config, 
                        'ica_files' : ica_files, 
                        'ica_IndstoNames' : ica_IndstoNames, 
                        'ica_ts' : ica_ts, 
                        'icn_files' : icn_files,
                        'icn_IndstoNames' : icn_IndstoNames, 
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
        elif not set(['config','ica_files','ica_IndstoNames','ica_ts',
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
            ica_IndstoNames        = analysisInfo['ica_IndstoNames'] # 4d nii indices for above ICA files
            ica_ts                 = analysisInfo['ica_ts'] # array of IC time series
            icn_files              = analysisInfo['icn_files'] # ICN template file paths
            icn_IndstoNames        = analysisInfo['icn_IndstoNames'] # 4d nii indices for above ICN files
            corrs                  = analysisInfo['corrs'] # dict of correlations, between ICA & ICN templates
            ica_icn_mapped         = analysisInfo['ica_icn_mapped'] # dict of ICA to ICN mappings (by files)
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
            
            # Load data into GUI variables
            self.config = InputHandling.config_check_defaults(config)
            
            self.add_files_to_list(self.listWidget_ICA, 'ica', 
                                   ica_files, file_inds=ica_IndstoNames,
                                   search_pattern=self.config['ica']['search_pattern'], 
                                   append=False)
            for lookup_key,ts in ica_ts.items():
                if lookup_key in self.gd['ica'].keys():
                    self.gd['ica'][lookup_key]['timeseries'] = np.array(ts)
            
            extra_template_items = self.config['icn']['extra_items'] + self.config['noise']['extra_items']
            self.add_files_to_list(self.listWidget_ICN, 'icn', 
                                   icn_files, file_inds=icn_IndstoNames,
                                   search_pattern=self.config['icn']['search_pattern'],
                                   extra_items=extra_template_items,
                                   append=False)
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
            
            # Remove ICA item from ICA listwidget (but not in gd['ica'])
            if not self.config['ica']['allow_multiclassifications']:
                ica_items = self.listWidget_ICA.findItems(ica_lookup, Qt.MatchExactly)
                for ica_item in ica_items:
                    self.listWidget_ICA.takeItem(self.listWidget_ICA.row(ica_item))

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
                
    @staticmethod
    def replace_faulty_config(config_file, mypath=None, config_backup=None):
        """Delete faulty config file, replace w/ backup config file"""
        
        if config_backup is None:
            if mypath is None:
                mypath = os.getcwd()
            backup_default = opj(mypath, 'config_settings', 'config_settings_backup.py')
            if os.path.isfile(backup_default):
                # load default backup configuration settings, saved as .py file
                from config_settings_backup import default_configuration as config_backup
            else:
                message = "Found faulty configuration file:  '" + fname + "''"
                message = "\nAdditionally, could not find default configuration background settings file: ''"
                message += backup_default
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
                mypath = configData['base_directory']
            else:
                mypath = os.getcwd()
        if config_backup is None:
            backup_default = opj(mypath, 'config_settings', 'config_settings_backup.py')
            if os.path.isfile(backup_default):
                # default backup configuration settings
                from config_settings_backup import default_configuration as config_backup
            else:
                message = "WARNING: could not find default configuration background settings file: ''"
                message += backup_default
                message += "'', display options & editing preferrence may be buggy!"
                print(message)

        # Check for defaults
        if 'base_directory' not in configData.keys(): 
            configData['base_directory'] = mypath
        if 'output_directory' not in configData.keys():
            configData['output_directory'] = mypath
        elif os.path.exists(opj(mypath, configData['output_directory'])):
            configData['output_directory'] = opj(mypath, configData['output_directory'])
        elif os.path.exists(configData['output_directory']):
            configData['output_directory'] = configData['output_directory']
        else: configData['output_directory'] = mypath
        if 'corr_onClick' not in configData.keys(): configData['corr_onClick'] = True
        if 'saved_analysis' not in configData.keys(): configData['saved_analysis'] = False
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

        # Load paths to MRI volumes
        if os.path.isfile(configData['icn']['directory']):
            configData['icn']['directory'] = os.path.dirname(configData['icn']['directory'])     
        if os.path.isfile(opj(mypath, configData['smri_file'])):
            configData['smri_file'] = opj(mypath, configData['smri_file'])
        
        return configData

