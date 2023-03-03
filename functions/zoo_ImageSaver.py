"""Functions used to save images & csv output as part of NetworkZoo"""

# Python Libraries
from os.path import join as opj  # method to join strings of file paths
from string import digits
import os, re
from math import ceil

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QThread, QRectF
from PyQt5.QtWidgets import QDialog
from PyQt5.QtGui import QColor, QPixmap, QPainter  #Qt fns. needed to draw png

from nilearn import image  # library for neuroimaging

# Output imports
import csv

# Internal imports
import zoo_ProgressBarWin as prbr    # PyQt widget in ../gui


class ImageSaver(QObject):
    """Creates concatenated images based off of Qt display,
    with both spatial maps & time series (~WYSIWYG from display)"""
    
    
    # Signals to interface to external fns.
    maxIJ_changed = pyqtSignal(int)
    ij_changed = pyqtSignal(int)
    ic_changed = pyqtSignal(str)
    templ_changed = pyqtSignal(str)
    interrupt_mapping = pyqtSignal(bool)
    ij_finished = pyqtSignal(bool)
    
    
    ### NOTES on inputs: ###
    #    'gd'                ~ NetworkZooGUI.gd
    #    'config'            ~ NetworkZooGUI.config
    #    'listWidget_mapped' ~ NetworkZooGUI.listWidget_mappedICANetworks
    #    'listWidget_ICN'    ~ NetworkZooGUI.listWidget_ICNtemplates
    #    'update_plots'      ~ NetworkZooGUI.update_plots
    #    'figure_x'          ~ NetworkZooGUI.figure_x
    #    'figure_t'          ~ NetworkZooGUI.figure_t
    #    'corrs'             ~ NetworkZooGUI.corrs
    #    'extra_items'  ~ NetworkZooGUI.config['icn']['extra_items']
    #                    +   NetworkZooGUI.config['noise']['extra_items']
    #    'output_path'  ~  path to save files, selected during NetworkZooGUI.generate_output
    # -All of the above args. have to be plugged into fn. apart from main window,
    #         to allow threading & progress bar gui to operate independently

    def __init__(self, gd, config,
                 listWidget_mapped, listWidget_ICN, update_plots, 
                 figure_x, figure_t, corrs,
                 extra_items=None, output_path=None):
        super().__init__()
        
        # Plugins to methods data containers, & Qt objects from NetworkZooGUI
        self.gd = gd
        self.config = config
        self.listWidget_mapped = listWidget_mapped
        self.listWidget_ICN = listWidget_ICN
        self.update_plots = update_plots
        self.figure_x = figure_x
        self.figure_t = figure_t
        self.corrs = corrs
        self.extra_items = extra_items
        self.output_path = output_path
        
        # Switch to interrupt loops when progress bar win is closed
        self.stopImageSaver = False
    
        # Output info
        self.concatFigureName = ''
        self.csvTableName = ''
        self.outputDir = ''
        self.output_files = []
        
        # # Reload all images before plotting, reseting to non-downscaled res.
        # self.reload_imgs()
    
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
    def interrupt(self, obj): #fn. called when window is closed
        self.stopImageSaver = True  #breaks loops
    
    def reload_img(self, filepath, vol_ind=0, fourD=False):
        """Reloads img, repeating original loading as part of NetworkZoo"""
        
        r_img = None
        if fourD and (vol_ind is not None):
            r_img = image.index_img(filepath, vol_ind)
        elif not fourD and (vol_ind > 0):
            img = image.load_img(filepath)
            r_img = image.new_img_like(img, img.get_fdata(caching='unchanged')==vol_ind, 
                                       copy_header=True)
        else:
            r_img = image.load_img(filepath)
        return r_img

    
    def reload_imgs(self):
        """Reloads all nifti vol. images, 
        for high-res. plotting after downsampling for display"""
        
        print('Reloading all images/volumes...')
        
        for listName in ['ica', 'icn']:
            for lookup in self.gd[listName].keys():
                if self.gd[listName][lookup]['img']:                
                    filepath = self.gd[listName][lookup]['filepath']
                    if os.path.exists(filepath):
                        vol_ind = self.gd[listName][lookup]['vol_ind']
                        fourD = self.gd[listName][lookup]['4d_nii']
                        self.gd[listName][lookup]['img'] = self.reload_img(filepath, 
                                                                           vol_ind=vol_ind, 
                                                                           fourD=fourD)
                
    
    
    @QtCore.pyqtSlot()
    def generate_output(self):
        """Create png w/ all mappings & associated csv file w/ mapping info,
        from ICA > ICN mappings specified by NetworkZooGUI"""
        
        # Sanity check
        if  not all(key in self.gd.keys() for key in ['mapped', 'mapped_ica']):
            print('ERROR: incorrectly formatted input arg: "gd" ')
            return
        elif len(self.gd['mapped'].keys()) == 0:
            message = 'WARNING: No ICA comp. > ICN template mappings currently set,'
            message +=' no output to generate!'
            print(message)
            return
            
            
        output_path = self.output_path
        output_files = []
        if output_path:
            if os.path.splitext(output_path)[-1] in ['.img', '.hdr', '.nii', '.csv', 
                                                     '.png', '.jpg', '.jpeg', '.csv', '.gz']:
                output_path = os.path.splitext(output_path)[0]
                if os.path.splitext(output_path)[-1] in ['.nii', '.tar']:
                    output_path = os.path.splitext(output_path)[0]
                
            # Output filenames w/o extensions:
            out_basename = os.path.basename(output_path)
            self.outputDir = os.path.dirname(output_path)
            if not os.path.exists(self.outputDir):
                os.makedirs(self.outputDir)
            #    Create name for single png with all spatial maps:
            self.concatFigureName = opj(self.outputDir, out_basename + '.png') 
            #    Create name for csv file for ICA spatial maps:
            self.csvTableName = opj(self.outputDir, out_basename + '.csv') 

            # GUI signal handling
            maxIJ = len(self.gd['mapped']) + 10
            self.maxIJ_changed.emit(maxIJ)
            ij = 0
        
            # Create png figure w/ ortho slices, time series & power spectrum
            if self.config['output']['create_figure']:
                figs_to_gzip = []
                images_to_concat = []
                images_to_concat_flagged = []
                images_ICA_fnames = []
                images_ICA_fnames_flagged = []
                images_ICN_names = []
                images_ICN_names_flagged = []
                
                for k, mapping_lookup in enumerate(self.gd['mapped'].keys()):
                    print('Creating subplots for mapping:  ' + mapping_lookup)
                    
                    if self.stopImageSaver: break   # called from outside fn., interrupts for loop
                    ij += 1
                    self.ij_changed.emit(ij)
                    self.ic_changed.emit(str(mapping_lookup))
                    
                    ica_lookup = self.gd['mapped'][mapping_lookup]['ica_lookup']
                    ica_name   = self.gd['mapped'][mapping_lookup]['ica_custom_name']
                    icn_lookup = self.gd['mapped'][mapping_lookup]['icn_lookup']
                    icn_name   = self.gd['mapped'][mapping_lookup]['icn_custom_name']
                    icn_name.strip('...') # "...non-template ICN", "...non-template Noise", etc.
                    
                    self.listWidget_mapped.setCurrentItem(self.gd['mapped'][mapping_lookup]['mapped_item'])
                    self.listWidget_ICN.setCurrentItem(self.gd['icn'][icn_lookup]['widget'])
                    self.update_plots()
                    
                    fname = opj(self.outputDir, '%s--%s.png' % (ica_name, icn_name))
                    fname_saved = ImageSaver.save_display(self.figure_x, self.figure_t, 
                                                          fname, cleanup=True)
                    
                    images_to_concat.append(fname_saved)
                    images_ICA_fnames.append(ica_name)
                    images_ICN_names.append(icn_name)
                    if re.match('\\.*noise', icn_lookup, flags=re.IGNORECASE):
                        images_to_concat_flagged.append(fname_saved)
                        images_ICA_fnames_flagged.append(ica_name)
                        images_ICN_names_flagged.append(icn_name)

                # Sort ICs alphabetically by ICA file names & append into noise ICs at end,
                #  where lambda fn. separates string w/ ',' then casts last part into digit if needed
                ICAnames_inds_sorted = sorted(range(len(images_ICA_fnames)), 
                                              key=lambda k: (int(images_ICA_fnames[k].partition(',')[-1]) 
                                                             if (images_ICA_fnames[k][-1].isdigit() 
                                                                 and ',' in images_ICA_fnames[k])
                                                             else float('inf')))
                #start w/ non-noise...
                images_to_concat = [images_to_concat[k] for k in ICAnames_inds_sorted] 
                #...add noise to end
                images_to_concat = images_to_concat + images_to_concat_flagged 
                #...& rm. earlier instance
                for flagged in images_to_concat_flagged: images_to_concat.remove(flagged)
                #...& ad infinitum
                images_ICA_fnames = [images_ICA_fnames[k] for k in ICAnames_inds_sorted]
                images_ICA_fnames = images_ICA_fnames + images_ICA_fnames_flagged
                for flagged in images_ICA_fnames_flagged: images_ICA_fnames.remove(flagged)
                images_ICN_names = [images_ICN_names[k] for k in ICAnames_inds_sorted]
                images_ICN_names = images_ICN_names + images_ICN_names_flagged
                for flagged in images_ICN_names_flagged: images_ICN_names.remove(flagged)

                # Create single png with all mappings
                if self.stopImageSaver: return   # called from outside fn., interrupts fn.
                self.ic_changed.emit('Concatenating all mapping figures...')
                print('Concatenating all mapping figures...')
                
                output_images = ImageSaver.concat_images(images_to_concat, self.concatFigureName,
                                                         max_rows=self.config['output']['figure_rows'],
                                                         max_cols=self.config['output']['figure_cols'],
                                                         concat_vertical=self.config['output']['concat_vertical'], 
                                                         cleanup=True)
                if output_images: output_files  += output_images
                if self.stopImageSaver: return   # called from outside fn., interrupts fn. 
                ij += len(images_to_concat)
                self.ij_changed.emit(ij)
                
                
            # Create csv w/ ICA networks & named ICN matches as columns
            #     NOTE: for completeness, all ICs in ICA list are included in table, 
            #              even if not mapped or in 4d Nifti
            if self.config['output']['create_table']:
                icn_info = {}
                i_key = -1
                ica_keys_unsorted = []
                for ica_lookup in self.gd['ica'].keys():
                    if self.stopImageSaver: break   # called from outside fn., interrupts for loop
                    if ica_lookup in self.gd['mapped_ica'].keys():
                        for icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                            if self.stopImageSaver: break
                            map_item = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                            mapping_lookup = str(map_item.data(Qt.UserRole))
                            self.ic_changed.emit(mapping_lookup)
                            ica_custom_name = self.gd['mapped'][mapping_lookup]['ica_custom_name']
                            icn_custom_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']

                            noise_id = 'noise' if re.match('\\.*noise', 
                                                           icn_lookup, 
                                                           flags=re.IGNORECASE) else 'ICN'
                            if icn_lookup in self.extra_items:
                                corr_r = float('inf')
                            elif ((self.corrs is not None) 
                                  and (ica_lookup in self.corrs.keys())
                                  and (icn_lookup in self.corrs[ica_lookup].keys())):
                                corr_r = '%0.2f' % self.corrs[ica_lookup][icn_lookup]
                            else:
                                corr_r = float('inf')
                            
                            i_key += 1
                            ica_keys_unsorted.append(ica_custom_name)
                            icn_info[i_key] = (ica_custom_name, icn_custom_name, noise_id, 
                                               icn_lookup, corr_r)

                # lambda fn. separates string w/ ',' then casts last part into digit if needed
                ica_keys_sorted = sorted(ica_keys_unsorted, 
                                         key=lambda item: (int(item.partition(',')[-1]) 
                                                           if (item[-1].isdigit() 
                                                               and ',' in item)
                                                           else float('inf')))
                icn_info_sorted = {}
                k_ord = -1
                for key in ica_keys_sorted:
                    k_ord += 1
                    k = ica_keys_unsorted.index(key)
                    icn_info_sorted[k_ord] = icn_info[k]
                    ica_keys_unsorted[k] = ''
                
                ij += 1
                self.ij_changed.emit(ij)
                self.ic_changed.emit('Exporting mappings as .csv file...')
                print('Exporting mappings as .csv file...')

                with open(self.csvTableName, 'w') as f:
                    writer = csv.writer(f)
                    writer.writerow(('ICA component:', 'ICN Label:', 'Noise Classification:', 
                                     'Template match:', 'Corr. w/ template:'))
                    for k in icn_info_sorted.keys():
                        writer.writerow((icn_info_sorted[k][0], icn_info_sorted[k][1], 
                                         icn_info_sorted[k][2], icn_info_sorted[k][3], 
                                         icn_info_sorted[k][4]))
                output_files.append(self.csvTableName)
                ij += 1
                self.ij_changed.emit(ij)

            # Finalities
            self.output_files = output_files # list of all output files, for outside referrence
            self.ij_finished.emit(True)
                

    @staticmethod
    def save_display(figure_x, figure_t, fname=None, cleanup=True, output_dir=None): 
        """Copy current spatial maps & timeseries displays into new display & save"""
        
        
        ### NOTES on inputs: ###
        #     'figure_x', 'figure_t' specified as during NetworkZooGUI.__init___() & passed as args.
        if fname is None:
            fname, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Save Display As:", 
                                                             output_dir,
                                                             filter = "PNG(*.png)")
        if fname:
            if os.path.splitext(fname)[-1] in ['.jpeg', '.jpg', '.tiff', '.svg', '.gif']:
                title = "Warning"
                message = "Input Image Type: " + os.path.splitext(fname)[-1]
                message += "  not supported. Image will be saved as .png"
                QtWidgets.QMessageBox.warning(None, title, message)
                fname = os.path.splitext(fname)[0]
            elif os.path.splitext(fname)[-1] == '.png':
                fname = os.path.splitext(fname)[0]
            fig_pieces = []
            
            # Save time/freq. info & spatial map, skip if time not displayed
            save_timefreq_plot =  False
            if (len(figure_t.get_axes())) > 0:
                save_timefreq_plot =  True

            # Save figures 
            if save_timefreq_plot: 
                # note that since figure_x & figure_t are seprate plots, need to be saved separately                
                fname_x = fname + "_spatialMap.png"
                fig_pieces.append(fname_x)
                figure_x.savefig(fname_x, format='png', pad_inches=0)
                
                fname_t = fname + "_timePlot.png"
                fig_pieces.append(fname_t)
                figure_t.savefig(fname_t, format='png', pad_inches=0)
                
                fname_concat = ImageSaver.concat_images(fig_pieces, fname, cleanup=cleanup)
                if len(fname_concat) == 1: fname_concat = fname_concat[0]
                return fname_concat
            
            else:   # Save spatial map only, no need to concat spatial & time plots
                fname_x = fname + ".png"
                figure_x.savefig(fname_x, format='png', pad_inches=0)
                return fname_x
            

    @staticmethod
    def concat_images(fig_pieces, fname, cleanup=True, max_rows=10, max_cols=1, 
                      concat_vertical=True, recurse_call=False):
        """Concatenates saved images into single file, using PyQt5"""
        
        if len(fig_pieces) == 0: return
        
        output_images = []
        
        max_rows = max(1, max_rows)
        max_cols = max(1, max_cols)
        if os.path.splitext(fname)[-1] != '.png':
            fname = fname + '.png'
                    
        # Get dimensions of figure pieces
        pixmaps = []
        pixmap_widths = []
        pixmap_heights = []
        for piece in fig_pieces:
            pixmap = QPixmap(piece)
            pixmap_widths.append(pixmap.size().width()) 
            pixmap_heights.append(pixmap.size().height())
            
        # Rough dims. of concatenated figure
        N = len(fig_pieces)
        if concat_vertical:
            if N <= max_rows:
                D1,D2 = N,1 # plot single col.
            else:
                D1 = min(N, max_rows) # rows as 1st dim...
                D2 = min(ceil(N / D1), max_cols) # ...& cols. as 2nd
                # D2 = min(max((N + (N % D1)) // D1, 1), max_cols) # ...& cols. as 2nd  # 7/7/2022 --kw-- debugging
                # D2 = min(max((N+D1) // D1, 1), max_cols) # & cols. as 2nd  # 6/8/2022 --kw-- debugging, incorrect calc. of lines                
        else:
            if N <= max_cols:
                D1,D2 = N,1 # plot single row
            else:
                D1 = min(N, max_cols) # cols as 1st dim...
                D2 = min(ceil(N / D1), max_rows) # ...& rows as 2nd
                # D2 = min(max((N + (N % D1)) // D1, 1), max_rows) # ...& rows as 2nd  # 7/7/2022 --kw-- debugging
                # D2 = min(max((N+D1) // D1, 1), max_rows) # & rows as 2nd  # 6/8/2022 --kw-- debugging, incorrect calc. of lines
        Nmax = min(N, D1 * D2)
            
        # Arrange figure pieces & Ensure dimensions fit within QPixMap limits
        pixmap_lim_check = True
        while (Nmax > 0) and pixmap_lim_check:
            fig_pieces_unarranged = fig_pieces[0:Nmax]
            pixmap_w_unarranged = pixmap_widths[0:Nmax]
            pixmap_h_unarranged = pixmap_heights[0:Nmax]
            fig_pieces_arranged = [] #ordered by entry into cue
            pixmap_w_arranged = [] #widths for above, equiv. ordering
            pixmap_h_arranged = [] #hieght for above, equiv. ordering
            pixmap_w_totals = [] #widths of slices, by row/col depending on concat_vertical
            pixmap_h_totals = [] #heights of slices (by row/col depending on   "     "
            for d2 in range(D2): #outer loop is non-concat. direction
                fig_pieces_slice = []
                pixmap_w_slice = []
                pixmap_h_slice = []
                for d1 in range(min(D1, len(fig_pieces_unarranged))):
                    fig_pieces_slice.append(fig_pieces_unarranged.pop(0))
                    pixmap_w_slice.append(pixmap_w_unarranged.pop(0))
                    pixmap_h_slice.append(pixmap_h_unarranged.pop(0))
                fig_pieces_arranged.append(fig_pieces_slice)
                pixmap_w_arranged.append(pixmap_w_slice)
                pixmap_h_arranged.append(pixmap_h_slice)
                if concat_vertical:
                    pixmap_w_totals.append(max(pixmap_w_slice)) #col. width
                    pixmap_h_totals.append(sum(pixmap_h_slice)) #concat. col. height
                else:
                    pixmap_w_totals.append(sum(pixmap_w_slice)) #concat. row width
                    pixmap_h_totals.append(max(pixmap_h_slice)) #row height
            if concat_vertical:
                dim_sizes = [sum(pixmap_w_totals),max(pixmap_h_totals)]
            else:
                dim_sizes = [max(pixmap_w_totals),sum(pixmap_h_totals)]
            if max(dim_sizes) > 2**15: # max. pixels on any dim = 2^15
                if dim_sizes[0] > 2**15: # width exceeds limits, adjust & try again
                    if concat_vertical:
                        Nadjust = D1 # fig. pieces per col.
                        D2 = D2 - 1 # reduce cols. by 1
                    else:
                        Nadjust = D2 # fig. pieces per col.
                        D1 = D1 - 1 # reduce cols. by 1
                elif dim_sizes[1] > 2**15: # height exceeds limits, adjust & try again
                    if concat_vertical:
                        Nadjust = D2 # fig. pieces per row
                        D1 = D1 - 1 # reduce rows by 1
                    else:
                        Nadjust = D1 # fig. pieces per row
                        D2 = D2 - 1 # reduce cols. by 1
                Nmax = Nmax - Nadjust
            else:
                pixmap_lim_check = False # pixels in both dims under Qt limits, exit loop
        if Nmax <= 0:
            message = "Unable to concatenate images, one/both dimension(s) exceeds pixel limits!"
            print(message)
            return output_images
        elif Nmax < N:
            message = "Concatenating images into multiple figures,"
            message += " in accordance with input parameters & pixel limits"
            print(message)
        
        # Assemble & concatenate figs. exceeding parameters/pixmap limits
        fig_pieces_leftover = fig_pieces[Nmax:N]
        if len(fig_pieces_leftover) > 0:
            fname = os.path.splitext(fname)[0]
            m = re.search(r'\d+$', fname)
            if m is None: #if fname does not end in a digit...
                fname_leftover = fname + '2.png'
                fname += '1.png'
            elif not recurse_call:  #if this is the first call to fn. & fname already ends in a digit...
                fname_leftover = fname + '_2.png'
                fname += '_1.png'
            else: #assume this is a recursive call to fn...
                # index digit for recursion already added by prev. fn. call...
                fname_leftover = re.sub(r'\d+$', '', fname) 
                fname_leftover += str(int(m.group()) + 1) + '.png'
                fname += '.png'
            
            # Recursive call, using subset of figures
            recursive_images = ImageSaver.concat_images(fig_pieces_leftover, fname_leftover,
                                                        cleanup=cleanup,
                                                        max_rows=max_rows,
                                                        max_cols=max_cols,
                                                        concat_vertical=concat_vertical,
                                                        recurse_call=True)
            output_images += recursive_images
        
            
        # Assemble & concatenate figure pieces
        x_start, x_end, y_start, y_end = 0, 0, 0, 0
        pixCanvas = QPixmap(dim_sizes[0], dim_sizes[1])
        painter = QPainter(pixCanvas)
        for d2 in range(len(fig_pieces_arranged)):
            for d1 in range(len(fig_pieces_arranged[d2])):
                piece = fig_pieces_arranged[d2][d1]
                pixmap = QPixmap(piece)
                qrect = QRectF(x_start, y_start, 
                               pixmap_w_arranged[d2][d1],
                               pixmap_h_arranged[d2][d1])
                painter.drawPixmap(qrect, pixmap, QRectF(pixmap.rect()))
                if concat_vertical:
                    y_start = y_start + pixmap_h_arranged[d2][d1]
                else:
                    x_start = x_start + pixmap_w_arranged[d2][d1]
            if concat_vertical:
                x_start = x_start + max(pixmap_w_arranged[d2])
                y_start = 0
            else:
                x_start = 0
                y_start = y_start + max(pixmap_h_arranged[d2])
        success = painter.end()
        if success:
            success = pixCanvas.save(fname, "PNG")
            output_images.append(fname)
        if success and cleanup:
            for fig_file in fig_pieces:
                if os.path.isfile(fig_file):
                    os.remove(fig_file)
        return output_images

                
                
class newDialogMod(QDialog):
    """Modification of QDialog, to close processing thread when window is closed"""
    
    def changeWindowTitle(self, newTitle):
        """Interface to change display window title from outside class"""
        newTitle = str(newTitle)
        self.setWindowTitle(newTitle)
        
    def linkThread(self, obj):
        self.linkedThread = obj
    def linkMapper(self, obj):
        self.mapper = obj
        
    def closeEvent(self, event):
        """over-rides default class method"""
        self.mapper.interrupt(True) #stops ongoing mapper fn.
        if self.linkedThread:
            self.linkedThread.quit()
            self.linkedThread.wait()
        event.accept()
        
        
        
class PatienceTestingGUI(QDialog, prbr.Ui_Dialog):
    """Encompass both progress bar GUI & processing output, with Q threading,
    here applied to generate_output()"""
    
    def __init__(self, *args, **kwargs):    
        super(self.__class__, self).__init__()
        
        # Set up new window
        newWin = newDialogMod(self)
        self.setupUi(newWin)
        
        newTitle = 'Creating Figures & Spreadsheet for Mappings:'
        newWin.changeWindowTitle(newTitle)
        self.CorrAmpersand.setText('')
        self.ICN_templateName.setText('')
        
        # Setup Correlation fns.
        self.output = ImageSaver(*args, **kwargs)
        
        # Connect signals to GUI
        self.output.registerSignal_maxIJ(self.progressWait.setMaximum)
        self.output.registerSignal_ij(self.progressWait.setValue)
        self.output.registerSignal_ic(self.ic_fileName.setText)
        self.output.registerSignal_templ(self.ICN_templateName.setText)
        self.output.ij_finished.connect(newWin.close)
        
        # Create thread for corr. fn. to run in background
        thread = QThread(self)
        self.output.moveToThread(thread)
        newWin.linkThread(thread)
        newWin.linkMapper(self.output)
        thread.started.connect(self.output.generate_output)
        thread.start()
        
        newWin.exec()
