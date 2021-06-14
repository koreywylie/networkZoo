# Mathematical/Neuroimaging/Plotting Libraries
import os, sys, re, json, csv
from os.path import join as opj  # method to join strings of file paths
import numpy as np
from nilearn import plotting, image, input_data  # library for neuroimaging
from nilearn import masking
from scipy.ndimage import binary_dilation #used to smooth edges of binary masks
from nibabel.nifti1 import Nifti1Image, Nifti1Pair
from nibabel.affines import apply_affine

# Qt GUI Libraries
from PyQt5 import QtWidgets


class MaskMaker(object):
    """fMRI mask creation for Network Zoo,
    binary mask created by thresholding classified component & applying ICN template name"""
    
    def __init__(self, gd, config=None):
        super().__init__()
        
        # Connections to data containers in Network Zoo script
        self.gd = gd # NetworkZooGUI.gd
        
        # Default specifications for mask
        self.mask_specs = {'mask_dtype': np.bool_, # data type for saved masks
                           'thresh_percentile': True, # threshold masks based on sample percentiles?
                           'thresh_max': True,       # threshold mask based on fraction of top value?
                           'smooth_mask': True,      # dilate & smooth mask, to fill in holes & improve fit
                           'cutoff_percentile': 99.,   # if thresh_q, top __% of voxels included in mask
                           'cutoff_fractMax': 0.33   # if thresh_max, faction of max value used for cutoff
                          }
        if config:
            if 'masks' in config.keys():
                if 'mask_dtype' in config['masks'].keys():
                    if config['masks']['mask_dtype'] == 'np.bool_':
                        self.mask_specs.update({'mask_dtype': np.bool_})
                if 'thresh_percentile' in config['masks'].keys():
                    self.mask_specs.update({'thresh_percentile': config['masks']['thresh_percentile']})
                if 'cutoff_percentile' in config['masks'].keys():
                    self.mask_specs.update({'cutoff_percentile': config['masks']['cutoff_percentile']})
                if 'thresh_max' in config['masks'].keys():
                    self.mask_specs.update({'thresh_max': config['masks']['thresh_max']})
                if 'cutoff_fractMax' in config['masks'].keys():
                    self.mask_specs.update({'cutoff_fractMax': config['masks']['cutoff_fractMax']})
                if 'smooth_mask' in config['masks'].keys():
                    self.mask_specs.update({'smooth_mask': config['masks']['smooth_mask']})

    
    def create_binaryMasks(self, mask_fname):
        """Create binary masks from mapped ICA components"""
                
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

        title = 'Created masks from classified ICs'
        message = ''
        if self.mask_specs['thresh_percentile']:
            message += 'Classified ICs thresholded using the top '
            message += str(int(self.mask_specs['cutoff_percentile'])) + '% of voxels. '
        if self.mask_specs['thresh_max']:
            message += 'Classified ICs thresholded using '
            message += str(self.mask_specs['cutoff_fractMax'])+' * maximum value. '
        message += '\n\nCreated files:'
        message += '\n  ' + os.path.basename(mask_fname) + ': 4D-nifti containing ICs classified as ICNs'
        message += '\n  ' + os.path.basename(csv_fname) + ': ICN names/labels for above nifti'
        message += '\n\nFiles created in:\n  ' + mask_dir
        QtWidgets.QMessageBox.information(None, title, message)

        # Create 4D nifti binary mask
        mask_noise = []
        mask_imgs = []
        mask_names = []

        # lambda fn. below separates string w/ '>' then casts last part into digit if needed
        for mapping_lookup in sorted(self.gd['mapped'].keys(), 
                                     key=lambda item: (int(item.partition('>')[-1]) if
                                                       item.partition('>')[-1].isdigit() else
                                                       float('inf'))):
            ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
            icn_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
            if re.match('\\.*noise', icn_name, flags=re.IGNORECASE):
                mask_noise.append('noise')
            else:
                mask_noise.append('ICN')

            ica_img = image.copy_img(self.gd['ica'][ica_lookup]['img'])
            ica_dat = ica_img.get_fdata(caching='unchanged')
            ica_dat[np.isnan(ica_dat)] = 0
            if self.mask_specs['thresh_percentile']:
                threshold = np.percentile(ica_dat, self.mask_specs['cutoff_percentile'])
                ica_dat[ica_dat < threshold] = 0
            if self.mask_specs['thresh_max']:
                threshold = ica_dat.max() * self.mask_specs['cutoff_fractMax']
                ica_dat[ica_dat < threshold] = 0
            ica_dat[ica_dat > 0] = 1
            if self.mask_specs['smooth_mask']:
                ica_dat = binary_dilation(ica_dat) #smooths edges & fills holes in mask
                ica_dat = binary_dilation(ica_dat) #repeat, further smoothing
            new_ica_img = image.new_img_like(ica_img, ica_dat, copy_header=True)
            mask_imgs.append(new_ica_img)
            mask_names.append(icn_name)
        image.concat_imgs(mask_imgs, 
                          dtype=self.mask_specs['mask_dtype'], 
                          auto_resample=True).to_filename(mask_fname)

        # Create csv w/ ICA networks & named ICN matches as columns
        icn_info = {}
        for k,icn_name in enumerate(mask_names):
            ic_name = mask_basename + ',%d' %(k+1)
            icn_info[ic_name] = (icn_name, mask_noise[k])
        with open(csv_fname, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(('ICA component:', 'ICN Label:', 'Noise Classification:'))
            
            #lambda separates string w/ ',' then casts last part into digit if needed
            for ic in sorted(icn_info.keys(), 
                             key=lambda item: (int(item.partition(',')[-1]) if 
                                               item[-1].isdigit() else 
                                               float('inf'))):
                writer.writerow((ic, icn_info[ic][0], icn_info[ic][1]))

