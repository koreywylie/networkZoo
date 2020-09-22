import numpy as np
from nilearn import image
from nibabel.nifti1 import Nifti1Image, Nifti1Pair
from nibabel.affines import apply_affine

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog
import zoo_progressBar as prbr    # PyQt widget in ../gui

class MapperThread(QtCore.QObject):
# class Mapper(object):
    """
    Rank each file in `in_files` against the `map_files` templates. Ranking is performed by computing the Matthews
    Correlation Coeficient (Phi-correlation coefficient), which is useful for binary vector correlations. Similar in
    interpretation to the Pearson Coefficient, this value ranges from -1 to 1, were -1 implies a anti-correlation,
    0 implies no correlation at at, and 1 is a perfect positive correlation.
    """
    
    maxIJ_changed = QtCore.pyqtSignal(int)
    ij_changed = QtCore.pyqtSignal(int)
    ic_changed = QtCore.pyqtSignal(str)
    templ_changed = QtCore.pyqtSignal(str)
    interrupt_mapping = QtCore.pyqtSignal()
    ij_finished = QtCore.pyqtSignal()

    
    
    
    def __init__(self,
                 map_files, map_filenames=None, 
                 in_files=None, in_filenames=None,
                 binerize_mapFiles=True, binerize_inFiles=False,
                 waitBar=False):
        super().__init__()
        
        # in_files & map files
        self.in_files, self.map_files = in_files, map_files
        self.in_filenames, self.map_filenames = in_filenames, map_filenames
        
        # thresh to create binary templates
        self.bin_mapFiles, self.bin_inFiles = binerize_mapFiles, binerize_inFiles
        
        self.waitBar = waitBar
        self.stopMapper = False
        
#         if waitBar:     # 7/11/2020 --kw-- avoids pyqtSignal has no attribute connect error, prob. w/ 'Mapper' object has no attributed maxIJ_changed, when signal is emitted
#             maxIJ_changed = QtCore.pyqtSignal(int)
#             ij_changed = QtCore.pyqtSignal(int)
#             ic_changed = QtCore.pyqtSignal(str)
#             templ_changed = QtCore.pyqtSignal(str)

#         if waitBar:   # 7/11/2020 --kw-- does not get to above error, but results in pyqtSignal has no attribute 'connect' error
#             self.ij_changed = QtCore.pyqtSignal(int)
#             self.maxIJ_changed = QtCore.pyqtSignal(int)
#             self.ic_changed = QtCore.pyqtSignal(str)
#             self.templ_changed = QtCore.pyqtSignal(str)
            
            
            
            
        if not hasattr(self, 'corr'): self.corr = {} #do not overwrite existing corrs.
#         self.corr = {}
        self.matches = {}
        self._load_files()
        self.get_ref_vol()
        
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
        self.stopMapper = True  #breaks for loops
        

    def _load_files(self):
        self.corr = {}
        self.in_imgs = [i if isinstance(i, (Nifti1Image, Nifti1Pair)) else image.load_img(i) for i in self.in_files]
        self.map_imgs = [i if isinstance(i, (Nifti1Image, Nifti1Pair)) else image.load_img(i) for i in self.map_files]
        
    def get_ref_vol(self):
        """Find smaller of 'in_files' or 'map_files' in terms of volume dimensions"""
        if isinstance(self.in_imgs[0], (Nifti1Image, Nifti1Pair)):
            img = self.in_imgs[0]
        else:
            img = image.load_img(self.in_imgs[0])
        if isinstance(self.map_imgs[0], (Nifti1Image, Nifti1Pair)):
            map_img = self.map_imgs[0]
        else:
            map_img = image.load_img(self.map_imgs[0])
        if img.shape[0:3] < map_img.shape[0:3]:
            self.reference_img = img
        elif img.shape[0:3] > map_img.shape[0:3]:
            self.reference_img = map_img
        else:
            self.reference_img = None
            
    def run(self):
        """Generate correlations, find top matches, choose best fit"""
        corr = self.spatial_correlations(imgs=self.in_imgs,           map_imgs=self.map_imgs,
                                         img_names=self.in_filenames, map_names=self.map_filenames,
                                         bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
                                         ref_img=self.reference_img)
        self.ij_finished.emit()
        return corr

#         self.corr = Mapper.spatial_correlations(self,
#                                                 imgs=self.in_imgs,           map_imgs=self.map_imgs, 
#                                                 img_names=self.in_filenames, map_names=self.map_filenames, 
#                                                 bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
#                                                 ref_img=self.reference_img)
#         if not self.stopMapper: self.assign_matches()
#         self.assign_matches()

    def run_one(self, in_imgs=None, in_img_names=None, map_imgs=None, map_names=None):
        if (in_img_names is None) and (map_names is None): return #nothing to do
        elif (in_img_names) and (in_imgs is None): return
        elif (map_names) and (map_imgs is None): return
        else:
            if in_imgs is None: in_imgs = self.in_imgs
            elif isinstance(in_imgs, (Nifti1Image, Nifti1Pair)): in_imgs = [in_imgs]
            else: return
            if in_img_names is None: in_img_names = self.in_filenames
            elif isinstance(in_img_names, str): in_img_names = [in_img_names]
            elif hasattr(in_img_names, '__len__'):
                if (len(in_img_names) != len(in_imgs)): return
            if map_imgs is None: map_imgs = self.map_imgs
            elif isinstance(map_imgs, (Nifti1Image, Nifti1Pair)): map_imgs = [map_imgs]
            else: return
            if map_names is None: map_names = self.map_filenames
            elif isinstance(map_names, str): map_names = [map_names]
            elif hasattr(map_names, '__len__'):
                if (len(map_names) != len(map_imgs)): return
        new_corr = self.spatial_correlations(imgs=in_imgs,    map_imgs=map_imgs, 
                                             img_names=in_img_names,      map_names=map_names,
                                             bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
                                             ref_img=self.reference_img)
#         new_corr = Mapper.spatial_correlations(self,
#                                                imgs=in_imgs,    map_imgs=map_imgs, 
#                                                img_names=in_img_names,      map_names=map_names,
#                                                bin_imgs=self.bin_inFiles,   bin_maps=self.bin_mapFiles,
#                                                ref_img=self.reference_img)
        for name1 in new_corr.keys():
            if name1 in self.corr.keys():
                for name2 in new_corr[name1].keys():
                    self.corr[name1].update({name2: new_corr[name1][name2]})
            else:
                self.corr.update({name1: new_corr[name1]})
        return new_corr

#     def get_top_matches(self, in_file, num_matches=None):
#         corr = self.corr[in_file].items() if in_file in self.corr.keys() else self.spatial_correlations(image.load_img(in_file))
#         corr = [(x,y) for x,y in corr]
#         corr.sort(key=(lambda x: x[1]), reverse=True)
#         if isinstance(num_matches, int):
#             corr = corr[0:num_matches]
#         return corr

#     def assign_matches(self, minimum_correlation=0.3, null_network=None, allow_copies=True):
#         """Return best match based on correlation."""
#         for in_file in self.in_filenames:
#             top_corrs = self.get_top_matches(in_file, num_matches=3)
            
#             if len(top_corrs) < 2:
#                 self.matches[in_file] = top_corrs[0][0]
#             elif top_corrs[0][1] >= minimum_correlation and top_corrs[0][1] >= 2*top_corrs[1][1]: 
#                 # mark "unambigous" associations, skip during manual mapping procedure
#                 self.matches[in_file] = top_corrs[0][0]
#             else:
#                 self.matches[in_file] = null_network
#         return self.matches
    

    @QtCore.pyqtSlot()
    def spatial_correlations(self,
                             imgs,      map_imgs, 
                             img_names, map_names, 
                             bin_imgs=False, bin_maps=True, ref_img=None):
        
        """Rank the `imgs` against each `map_files` templates"""

        I = len(img_names)
        J = len(map_names)
        self.maxIJ_changed.emit(I*J)
        
        corr = {}
        if self.waitBar: ij = 0
        imgs = imgs if hasattr(imgs, '__iter__') else [imgs]  # make iterable
        map_imgs = map_imgs if hasattr(map_imgs, '__iter__') else [map_imgs]  # make iterable
        for i, img in enumerate(imgs):
            if self.stopMapper: break
            print('Correlating...'+img_names[i]+'...')
            if self.waitBar: self.ic_changed.emit(img_names[i])
            
            corr[img_names[i]] = {}
            if ref_img is None:  #default to rescaling to dimensions of img, if not input
                ref_img = img
            if bin_imgs:         #binarize w/o scaling or thresholding
                img_arr = self.prep_tmap(img, reference=ref_img, binary=True)
            else:                #treats imgs as array of real numbers, threshold & scale appropriately
                img_arr = self.prep_tmap(img, reference=ref_img, 
                                         scale=True, quantile=75, threshold=1, binary=False)                
#             if bin_imgs:         #binarize w/o scaling or thresholding
#                 img_arr = Mapper.prep_tmap(img, reference=ref_img, binary=True)
#             else:                #treats imgs as array of real numbers, threshold & scale appropriately
#                 img_arr = Mapper.prep_tmap(img, reference=ref_img, 
#                                            scale=True, quantile=75, threshold=1, binary=False)
            for ii, mimg in enumerate(map_imgs):
                if self.stopMapper: break
                print('Correlating   %s   &   %s...' % (img_names[i], map_names[ii]))
                if self.waitBar:
                    self.templ_changed.emit(map_names[ii])
                    ij += 1
                    self.ij_changed.emit(ij)
                if bin_maps:     #treats mimgs as binary ICNs templates, binarize w/o scaling or thresholding
                    mimg_arr = self.prep_tmap(mimg, reference=ref_img, binary=True)
                else:            #treats mimgs as array of real numbers, threshold & scale appropriately
                    mimg_arr = self.prep_tmap(mimg, reference=ref_img, 
                                              scale=True, quantile=75, threshold=1, binary=False)
                
#                 if bin_maps:     #treats mimgs as binary ICNs templates, binarize w/o scaling or thresholding
#                     mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img, binary=True)
#                 else:            #treats mimgs as array of real numbers, threshold & scale appropriately
#                     mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img, 
#                                                 scale=True, quantile=75, threshold=1, binary=False)
                corr[img_names[i]][map_names[ii]] = np.corrcoef(mimg_arr, img_arr)[0,1]    
        return corr
    
    
#    @staticmethod
#     def prep_tmap(img, reference=None, center=False, scale=False, threshold=0.2, quantile=None, binary=True):
    def prep_tmap(self, img, reference=None, center=False, scale=False, threshold=0.2, quantile=None, binary=True):

        if isinstance(img, (Nifti1Image, Nifti1Pair)):
            img = img
        elif img is None and isinstance(reference, (Nifti1Image, Nifti1Pair)):
            img = reference
        else:
            image.load_img(img)
        if isinstance(reference, (str, (Nifti1Image, Nifti1Pair))):
            dat = image.resample_to_img(source_img=img, target_img=reference).get_data().flatten()
        else:
            dat = img.get_data().flatten()
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

#     @staticmethod
#     def spatial_correlations(self,
#                              imgs,      map_imgs, 
#                              img_names, map_names, 
#                              bin_imgs=False, bin_maps=True, ref_img=None,
#                              maxIJ=None, changeij=None, icChange=None, templChange=None
#                             ):
#         """Rank the `imgs` against each `map_files` templates"""
        


# #         # testmark1
        
    
#         if maxIJ:
#             I = len(img_names)
#             J = len(map_names)
#             maxIJ.emit(I*J)
            
            

        
#         corr = {}
#         if self.waitBar: ij = 0
#         imgs = imgs if hasattr(imgs, '__iter__') else [imgs]  # make iterable
#         map_imgs = map_imgs if hasattr(map_imgs, '__iter__') else [map_imgs]  # make iterable
#         for i, img in enumerate(imgs):
#             # print('Correlating:  '+img_names[i]+'...')
#             if self.waitBar: self.ic_changed.emit(img_names[i])
            
#             corr[img_names[i]] = {}
#             if ref_img is None:  #default to rescaling to dimensions of img, if not input
#                 ref_img = img
#             if bin_imgs:         #binarize w/o scaling or thresholding
#                 img_arr = Mapper.prep_tmap(img, reference=ref_img, binary=True)
#             else:                #treats imgs as array of real numbers, threshold & scale appropriately
#                 img_arr = Mapper.prep_tmap(img, reference=ref_img, 
#                                            scale=True, quantile=75, threshold=1, binary=False)
#             for ii, mimg in enumerate(map_imgs):
#                 print('Correlation  %s  &   %s...' % (img_names[i], map_names[ii]))
#                 if self.waitBar:
#                     self.templ_changed.emit(map_names[ii])
#                     ij += 1
#                     self.ij_changed.emit(ij)
                
#                 if bin_maps:     #treats mimgs as binary ICNs templates, binarize w/o scaling or thresholding
#                     mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img, binary=True)
#                 else:            #treats mimgs as array of real numbers, threshold & scale appropriately
#                     mimg_arr = Mapper.prep_tmap(mimg, reference=ref_img, 
#                                                 scale=True, quantile=75, threshold=1, binary=False)
#                 corr[img_names[i]][map_names[ii]] = np.corrcoef(mimg_arr, img_arr)[0,1]    
#         return corr
        
        
# class PatientlyMappingInterface(QtCore.QObject):
#     """Interface between progress bar GUI & Mapper class"""
    
#     def __init__(self, *args, **kwargs):    
#         super(self.__class__, self).__init__()    
        
#         ### Setup Correlation fns. ###
#         kwargs.update({'waitBar': True})
#         self.mapper = Mapper(*args, **kwargs)
         


        
#         newWin = QDialog()  # will block main window, while running
#         patienceBar = prbr.Ui_Dialog() #class in progressBar.py
#         patienceBar.setupUi(newWin)
#         patienceBar.moveToThread(thread)
#         newWin.exec_()
        
#         return patienceBar
    
    
#     def setup_mapper(self):
#         ### Setup Correlation fns. ###
#         self.mapper = Mapper(self,
#                              map_files, map_filenames,
#                              in_files, in_filenames,
#                              waitBar=True)
        

        
class newDialogMod(QDialog):
    """Modification of QDialog, to close mapper thread when window is closed"""
    
#     def __init__(self):
#         super(self.__class__, self).__init__()
    
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
        event.accept()
        
        
        
class PatienceTestingGUI(QDialog, prbr.Ui_Dialog):
    """Encompass both progress bar GUI & mapping, with Q threading"""
    
    
    
    def __init__(self, *args, **kwargs):
        
        super(self.__class__, self).__init__()
        
        newWin = newDialogMod(self)
        
        # import pdb; pdb.set_trace()
        
        # newWin = QWidget()
        # newWin = QWidget(self)
#         newWin = QDialog()
#         newWin = QDialog(self)
        self.setupUi(newWin)
#         newWin.show()
#         newWin.exec()
        
    
    
    # 7/12/2020 --kw-- NOTE: still need to override default 'newWin.closeEvent' method, in order to shut down thread running corr. fn.
    
    
    
    
#         thread1 = QtCore.QThread(self)
#         newWin.moveToThread(thread1)
#         thread1.started.connect(newWin.exec)
#         thread1.start()
        
        # import pdb; pdb.set_trace()

        # 7/12/2020 --kw--  show() opens a nonmodal dialog, while .exec() below opens a model dialog (preferred)
#         self.show()
        # newWin.open()  #7/12/2020 --kw-- equivalent to show()
#         newWin.show()   # 7/11/2020 --kw-- opens blank window, of appropriate size, does not update
        # newWin.exec()  # 7/11/2020 --kw-- fn. will launch new dialogue window, the hang indefinetly until closed
        
        
        ### Setup Correlation fns. ###
        kwargs.update({'waitBar': True})
        self.mapper = MapperThread(*args, **kwargs)
        
        ### Connect signals to GUI ###
        self.mapper.registerSignal_maxIJ(self.progressWait.setMaximum)
        self.mapper.registerSignal_ij(self.progressWait.setValue)
        self.mapper.registerSignal_ic(self.ic_fileName.setText)
        self.mapper.registerSignal_templ(self.ICN_templateName.setText)
        self.mapper.ij_finished.connect(newWin.close)
        
        ### Create thread for corr. fn. to run in background ###
        thread2 = QtCore.QThread(self)
        self.mapper.moveToThread(thread2)
        newWin.linkThread(thread2)
        newWin.linkMapper(self.mapper)
        thread2.started.connect(self.mapper.run)
        
#         import pdb; pdb.set_trace()
#         thread1.start()        
#         self.mapper.run()

        thread2.start()

#         newWin.exec_() # no different than below
        newWin.exec()
        
        
        
        
#         import pdb; pdb.set_trace()
        
#         newWin = QDialog(self)
#         self.setupUi(newWin)
        
#         thread = QtCore.QThread(self)
#         thread.start()
        
#         import pdb; pdb.set_trace()
        
# #         newWin.moveToThread(thread)
        
# #         import pdb; pdb.set_trace()
        
#         newWin.exec_()
        
# #         import pdb; pdb.set_trace()
        
# #         thread.start()
        
        

        
        
        
#         self.patienceMeter = PatientlyMappingInterface(*args, **kwargs)
#         self.patienceMeter.moveToThread(thread)
        
#         # import pdb; pdb.set_trace()
        
#         self.patienceMeter.mapper.registerSignal_IJ(self.progressWait.setMaximum)
#         self.patienceMeter.mapper.registerSignal_ij(self.progressWait.setValue)
#         self.patienceMeter.mapper.registerSignal_ic(self.ic_fileName.setText)
#         self.patienceMeter.mapper.registerSignal_templ(self.ICN_templateName.setText)
        
    
        # newWin.exec_()

        
        