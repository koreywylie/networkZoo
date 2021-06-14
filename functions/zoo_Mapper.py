import numpy as np
from nilearn import image
from nibabel.nifti1 import Nifti1Image, Nifti1Pair
from nibabel.affines import apply_affine

from PyQt5 import QtCore
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QDialog, QPushButton

# Internal imports
import zoo_ProgressBarWin as prbr    # PyQt widget in ../gui

class Mapper(QObject):
    """
    Correlation fns. for Network Zoo GUI.
    
    Correlate each file in 'in_files' to each file in 'map_files'.  Typically, 'in_files' are
    IC components while 'map_files' are ICN templates.  Calculation is sped up by finding the
    smaller of the two vols., as well as by the option to binerize one or both vols.
       Following correlation, files can be ranked based on correlations from outside fn. calls
    to static methods
    """
    
    # Signals to interface to external fns.
    maxIJ_changed = pyqtSignal(int)
    ij_changed = pyqtSignal(int)
    ic_changed = pyqtSignal(str)
    templ_changed = pyqtSignal(str)
    interrupt_mapping = pyqtSignal()
    ij_finished = pyqtSignal()
    
    def __init__(self,
                 in_files=None, in_filenames=None,
                 map_files=None, map_filenames=None, 
                 bin_inFiles=False, bin_mapFiles=False,
                 waitBar=False, corrs=None):
        super().__init__()
        
        # in_files & map files
        self.in_files, self.map_files = in_files, map_files
        self.in_filenames, self.map_filenames = in_filenames, map_filenames
        
        # thresh to create binary templates
        self.bin_mapFiles, self.bin_inFiles = bin_mapFiles, bin_inFiles
        
        # list of images
        self.in_imgs = []
        self.map_imgs = []
        
        # vol. for downsizing
        self.reference_img = None

        
        # set-up queque for self.run_one() inputs
        self.queue_in_img_names = []
        self.queue_map_names = []
        
        # record of new & prev. calculated correlations
        self.new_corrs = {}
        if corrs is not None:
            self.corrs = corrs #dict w/ existing corrs., to prevent redundant calc.
        else:
            self.corrs = {}
        
        # switch for progress bar 
        self.waitBar = waitBar
        self.stopMapper = False  # called from outside fn., interrupts loop
        
        # load data & finalities
        self._load_files()
        
        #find smaller vol., used to downsample larger vol.
        if (len(self.in_imgs) > 0) and (len(self.map_imgs) > 0):
            self.set_ref_vol(img=self.in_imgs[0], 
                             map_img=self.map_imgs[0])
        
        
    # fns. to access signals from another class
    def registerSignal_maxIJ(self, obj):
        if (hasattr(self, 'maxIJ_changed')):
            self.maxIJ_changed.connect(obj)    
    def registerSignal_ij(self, obj):
        if (hasattr(self, 'ij_changed')):
            self.ij_changed.connect(obj)
    def registerSignal_ic(self, obj):
        if (hasattr(self, 'ic_changed')):
            self.ic_changed.connect(obj)
    def registerSignal_templ(self, obj):
        if (hasattr(self, 'templ_changed')):
            self.templ_changed.connect(obj)
    def interrupt(self): #fn. called when window is closed
        self.stopMapper = True  #breaks for loop(s), called from outside class
        

    def _load_files(self):
        """Initializes fn. by loading all images"""
        if self.in_files:
            self.in_imgs = [i if isinstance(i, (Nifti1Image, Nifti1Pair)) else image.load_img(i)
                            for i in self.in_files]
        if self.map_files:
            self.map_imgs = [i if isinstance(i, (Nifti1Image, Nifti1Pair)) else image.load_img(i)
                             for i in self.map_files]
        
    def set_ref_vol(self, img=None, map_img=None):
        """Find smaller of 'in_files' or 'map_files' in terms of volume dimensions"""
        
        if (img is None) and (map_img is None): return
        if isinstance(img, list): img = img[0]
        if isinstance(map_img, list): map_img = map_img[0]
        
        if not isinstance(img, (Nifti1Image, Nifti1Pair)):
            if hasattr(self, 'in_imgs'):
                if isinstance(self.in_imgs[0], (Nifti1Image, Nifti1Pair)):
                    img = self.in_imgs[0]
                else:
                    img = image.load_img(self.in_imgs[0])
        if not isinstance(map_img, (Nifti1Image, Nifti1Pair)):
            if hasattr(self, 'map_imgs'):
                if isinstance(self.map_imgs[0], (Nifti1Image, Nifti1Pair)):
                    map_img = self.map_imgs[0]
                else:
                    map_img = image.load_img(self.map_imgs[0])
                    
        if img and map_img:
            if img.shape[0:3] > map_img.shape[0:3]:
                self.reference_img = map_img
            else:
                self.reference_img = img
                
            
    def run(self):
        """Generate all correlations"""
        
        self.new_corrs = {}
        new_corrs = self.spatial_correlations(imgs=self.in_imgs,           map_imgs=self.map_imgs,
                                              img_names=self.in_filenames, map_names=self.map_filenames,
                                              bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
                                              ref_img=self.reference_img,  old_corrs=self.corrs)
        if self.waitBar: self.ij_finished.emit()
        self.new_corrs = new_corrs
        self.update_corrs(new_corrs)
                
        return new_corrs
    
    
    def run_one(self, in_imgs=None, in_img_names=None, map_imgs=None, map_names=None):
        """Run single/few corrs., selected by name if specified"""
        
        # corr. files in queue by default
        if in_img_names is None:
            if len(self.queue_in_img_names) > 0:
                in_img_names = self.queue_in_img_names
        if map_names is None:
            if len(self.queue_map_names) > 0:
                map_names = self.queue_map_names
        
        # sanity check(s)
        if ((in_img_names is None) and (map_names is None) and
            (in_imgs is None) and (map_imgs is None)): return #nothing to do
        
        # find loaded imgs by name
        if in_img_names is None:
            in_img_names = self.in_filenames
        elif isinstance(in_img_names, str):
            in_img_names = [in_img_names]
        if in_imgs is None:
            if in_img_names:
                in_imgs = []
                for name in in_img_names:
                    if name in self.in_filenames:
                        i = self.in_filenames.index(name)
                        in_imgs.append(self.in_imgs[i])
            else:
                in_imgs = self.in_imgs
        elif isinstance(in_imgs, (Nifti1Image, Nifti1Pair)): 
            in_imgs = [in_imgs]
        else: 
            return
        if (len(in_img_names) != len(in_imgs)):
            return
        if map_names is None:
            map_names = self.map_filenames
        elif isinstance(map_names, str):
            map_names = [map_names]
        if map_imgs is None:
            if map_names:
                map_imgs = []
                for name in map_names:
                    if name in self.map_filenames:
                        i = self.map_filenames.index(name)
                        map_imgs.append(self.map_imgs[i])
            else:
                map_imgs = self.map_imgs
        elif isinstance(map_imgs, (Nifti1Image, Nifti1Pair)): 
            map_imgs = [map_imgs]
        else:
            return
        if (len(map_names) != len(map_imgs)):
            return
            
        self.new_corrs = {}
        new_corrs = self.spatial_correlations(imgs=in_imgs,                map_imgs=map_imgs, 
                                              img_names=in_img_names,      map_names=map_names,
                                              bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
                                              ref_img=self.reference_img,  old_corrs=self.corrs)
        if self.waitBar: self.ij_finished.emit()
        self.new_corrs = new_corrs
        self.update_corrs(new_corrs)
                
        return new_corrs

    
    def update_corrs(self, new_corrs):
        """Updates existing corrs w/ contents of new_corrs"""
        
        for name1 in new_corrs.keys(): # update existing corrs.
            if name1 not in self.corrs.keys():
                self.corrs.update({name1: {}})
            if name1 in self.queue_in_img_names:
                self.queue_in_img_names.remove(name1)
            for name2 in new_corrs[name1].keys():
                self.corrs[name1].update({name2: new_corrs[name1][name2]})
                if name2 in self.queue_map_names:
                    self.queue_map_names.remove(name2)
    

    @QtCore.pyqtSlot()
    def spatial_correlations(self,
                             imgs,      map_imgs, 
                             img_names, map_names, 
                             bin_imgs=False, bin_maps=True, 
                             ref_img=None, old_corrs=None):
        """Correlate the `imgs` with each `map_files` templates"""

        I = len(img_names)
        J = len(map_names)
        self.maxIJ_changed.emit(I*J)
        
        if not old_corrs: old_corrs = {}
        new_corrs = {}
        ij = 0
        imgs = imgs if hasattr(imgs, '__iter__') else [imgs]  # make iterable
        map_imgs = map_imgs if hasattr(map_imgs, '__iter__') else [map_imgs]  # make iterable
        for i, img in enumerate(imgs):
            if self.waitBar: self.ic_changed.emit(img_names[i])
            if self.stopMapper:  # called from outside fn., interrupts for loop
                self.update_corrs(new_corrs)
                break  
            if img_names[i] in old_corrs.keys(): #skip redundant calc.
                if all(name in old_corrs[img_names[i]].keys() for name in map_names):
                    ij = ij + J
                    self.ij_changed.emit(ij)
                    continue
                        
            print('Correlating...'+img_names[i]+'...')
            new_corrs[img_names[i]] = {}
            if ref_img is None:  #default to rescaling to dimensions of img, if not input
                ref_img = img
            if bin_imgs:         #binarize w/o scaling or thresholding
                img_arr = Mapper.prep_tmap(img, reference=ref_img, binary=True)
            else:                #treats imgs as array of real numbers, threshold & scale appropriately
                img_arr = Mapper.prep_tmap(img, reference=ref_img)
            
            for ii, mimg in enumerate(map_imgs):
                if self.stopMapper:  # called from outside fn., interrupts for loop
                    self.update_corrs(new_corrs)
                    break 
                if img_names[i] in old_corrs.keys(): #skip redundant calc.
                    if map_names[ii] in old_corrs[img_names[i]].keys():
                        ij += 1
                        self.ij_changed.emit(ij)
                        continue
                
                print('Correlating   %s   &   %s...' % (img_names[i], map_names[ii]))
                if self.waitBar:
                    self.templ_changed.emit(map_names[ii])
                    ij += 1
                    self.ij_changed.emit(ij)
                if bin_maps: #treats mimgs as binary ICNs templates, binarize w/o scaling or thresholding
                    mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img, binary=True)
                else:        #treats mimgs as array of real numbers, threshold & scale appropriately
                    mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img)
                new_corrs[img_names[i]][map_names[ii]] = np.corrcoef(mimg_arr, img_arr)[0,1]    
        return new_corrs
    
    
    @staticmethod
    def prep_tmap(img, reference=None, center=False, scale=False, 
                  threshold=None, quantile=None, binary=False):
        """Quick transforms to speed corr. calc. for spatial maps"""
        
        if isinstance(img, (Nifti1Image, Nifti1Pair)):
            img = img
        elif img is None and isinstance(reference, (Nifti1Image, Nifti1Pair)):
            img = reference
        else:
            image.load_img(img)
        if isinstance(reference, (str, (Nifti1Image, Nifti1Pair))):
            if img.shape != reference.shape:
                img = image.resample_to_img(source_img=img, target_img=reference)
        dat = img.get_fdata(caching='unchanged').flatten()
        
        dat[np.logical_not(np.isfinite(dat))] = 0   # zero out all NaN, indexing syntax required by numpy
        if center:
            dat[dat.nonzero()] = dat[dat.nonzero()] - dat[dat.nonzero()].mean()
        if scale:
            if dat[dat.nonzero()].std(ddof=1) != 0:
                dat[dat.nonzero()] = dat[dat.nonzero()] / dat[dat.nonzero()].std(ddof=1)
        if quantile:
            dat[dat < np.percentile(dat[dat.nonzero()], quantile)] = 0.
        if threshold: # if threshold appears to be fraction, threshold vol. based on fraction of maximum
            if (0 < threshold < 1 < dat.max()): 
                threshold = dat.max() * threshold 
            dat[dat < threshold] = 0.
        if binary:    # note that prev. centering, quantiles, scaling will create 0 or neg. values
            dat[dat < 0] = 0.
            dat[dat.nonzero()] = 1.
        return dat

    @staticmethod
    def get_top_matches(in_file, in_file_corrs, num_matches=None):
        """Sort corelations in descending order, to find top matches for in_file"""
        if in_file not in in_file_corrs.keys(): return None
        
        corrs = in_file_corrs[in_file].items()
        corrs = [(x,y) for x,y in corrs]
        corrs.sort(key=(lambda x: x[1]), reverse=True)
        if isinstance(num_matches, int):
            corrs = corrs[0:num_matches]
        return corrs

    @staticmethod
    def assign_matches(in_files, in_file_corrs, 
                       min_corr=0.3, unambigous_scaling_factor=2):
        """Return best match based on correlation."""
        
        matches = {}
        null_network = None # match type returned for non-matched files
        for in_file in in_files:
            top_corrs = Mapper.get_top_matches(in_file, in_file_corrs, num_matches=3)
            
            if not top_corrs:
                matches[in_file] = null_network # None, or change as fn. arg.
            elif len(top_corrs) < 2:
                matches[in_file] = top_corrs[0][0]
            elif (top_corrs[0][1] >= min_corr and
                  (top_corrs[0][1] >= unambigous_scaling_factor*top_corrs[1][1])): 
                matches[in_file] = top_corrs[0][0]  # mark "unambigous" associations, 
                                                    #   skip during manual mapping procedure
            else:
                matches[in_file] = null_network # None, or change as fn. arg.
        return matches

        
        
class newDialogMod(QDialog):
    """Modification of QDialog, to close mapper thread when window is closed"""
        
    def linkThread(self, obj):
        self.linkedThread = obj
    def linkMapper(self, obj):
        self.mapper = obj
        
    def closeEvent(self, event):
        """over-rides default class method"""
        self.mapper.interrupt() #stops ongoing mapper fn.
        if self.linkedThread:
            self.linkedThread.quit()
            self.linkedThread.wait()
        if not isinstance(event, QtCore.QEvent):
            self.close()
        else:
            event.accept()
        
        
        
class PatienceTestingGUI(QDialog, prbr.Ui_Dialog):
    """Encompass both progress bar GUI & mapping, with Q threading"""
    
    def __init__(self, *args, **kwargs):    
        super(self.__class__, self).__init__()
        
        # Set up new window
        newWin = newDialogMod(self)
        self.setupUi(newWin)
        
        # Add Pause & Return button
        self.returnButton = QPushButton("Pause", parent=newWin)
        self.returnButton.move(158,150)
        self.returnButton.clicked.connect(newWin.closeEvent)
        
        
        # Setup Mapper fns. for correlation fns.
        kwargs.update({'waitBar': True}) #enable GUI connections to fns.
        reset_mapper = True
        if 'mapper' in kwargs.keys():
            reset_mapper = False
            if 'in_files' in kwargs.keys():
                if not (set(kwargs['in_files']) < set(kwargs['mapper'].in_files)):
                    reset_mapper = True # ...where "<" denotes set membership operator 
            if 'in_filenames' in kwargs.keys():
                if not (set(kwargs['in_filenames']) < set(kwargs['mapper'].in_filenames)):
                    reset_mapper = True
            if 'map_files' in kwargs.keys():
                if not (set(kwargs['map_files']) < set(kwargs['mapper'].map_files)):
                    reset_mapper = True # ...where "<" denotes set membership operator 
            if 'map_filenames' in kwargs.keys():
                if not (set(kwargs['map_filenames']) < set(kwargs['mapper'].map_filenames)):
                    reset_mapper = True
            if 'corrs' in kwargs.keys():
                if not (set(kwargs['corrs'].keys()) < set(kwargs['mapper'].corrs.keys())):
                    reset_mapper = True
                if len(kwargs['corrs'].keys()) > 0:
                    for key in kwargs['corrs'].keys():
                        if key not in kwargs['mapper'].corrs.keys():
                            reset_mapper = True
        if reset_mapper:
            kwargs.update({'waitBar': True})
            kwargs.pop('mapper', None)
            self.mapper = Mapper(*args, **kwargs) #enable GUI connections to fns.
        else:
            self.mapper = kwargs['mapper']
            self.mapper.waitBar = True
                    
        
        # Connect signals to GUI
        self.mapper.registerSignal_maxIJ(self.progressWait.setMaximum)
        self.mapper.registerSignal_ij(self.progressWait.setValue)
        self.mapper.registerSignal_ic(self.ic_fileName.setText)
        self.mapper.registerSignal_templ(self.ICN_templateName.setText)
        self.mapper.ij_finished.connect(newWin.close)
        
        # Create thread for corr. fn. to run in background
        thread = QThread(self)
        self.mapper.moveToThread(thread)
        newWin.linkThread(thread)
        newWin.linkMapper(self.mapper)
        thread.started.connect(self.mapper.run)
        thread.start()

        newWin.exec()

        
