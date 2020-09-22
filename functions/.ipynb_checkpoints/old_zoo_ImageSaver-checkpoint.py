# Python Libraries
from os.path import join as opj  # method to join strings of file paths
from string import digits
import os, re

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QThread, QRectF
from PyQt5.QtWidgets import QDialog
from PyQt5.QtGui import QColor, QPixmap, QPainter  #Qt fns. needed to draw png

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
    interrupt_mapping = pyqtSignal()
    ij_finished = pyqtSignal()
    
    
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

    def __init__(self, 
                 gd, listWidget_mapped, listWidget_ICN, update_plots, 
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
        self.stopImageSaver = True  #breaks loops
    
    
    @QtCore.pyqtSlot()
    def generate_output(self):
        """Create png w/ all mappings & associated csv file w/ mapping info,
        from ICA > ICN mappings specified by NetworkZooGUI"""
        
        # Sanity check
        if  not all(key in self.gd.keys() for key in ['mapped', 'mapped_ica']):
            print('ERROR: incorrectly formatted input arg: "gd" ')
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
            figs_to_gzip = []
            images_to_concat = []
            images_to_concat_flagged = []
            images_ICA_fnames = []
            images_ICA_fnames_flagged = []
            images_ICN_names = []
            images_ICN_names_flagged = []
            for k, mapping_lookup in enumerate(self.gd['mapped'].keys()):
                if self.stopImageSaver: break   # called from outside fn., interrupts for loop
                ij += 1
                self.ij_changed.emit(ij)
                self.ic_changed.emit(mapping_lookup)
                
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
            images_to_concat = [images_to_concat[k] for k in ICAnames_inds_sorted] #start w/ non-noise...
            images_to_concat = images_to_concat + images_to_concat_flagged #...add noise to end
            for flagged in images_to_concat_flagged: images_to_concat.remove(flagged) #...& rm. earlier occurences   
            images_ICA_fnames = [images_ICA_fnames[k] for k in ICAnames_inds_sorted] #...& ad infinitum
            images_ICA_fnames = images_ICA_fnames + images_ICA_fnames_flagged
            for flagged in images_ICA_fnames_flagged: images_ICA_fnames.remove(flagged)
            images_ICN_names = [images_ICN_names[k] for k in ICAnames_inds_sorted]
            images_ICN_names = images_ICN_names + images_ICN_names_flagged
            for flagged in images_ICN_names_flagged: images_ICN_names.remove(flagged)
                
            # Create single png with all mappings
            if self.stopImageSaver: return   # called from outside fn., interrupts fn.
            self.ic_changed.emit('Concatenating all mapping figures...')
            
            output_images = ImageSaver.concat_images(images_to_concat, self.concatFigureName,
                                                     concat_vertical=True, cleanup=True)
            output_files  += output_images
            if self.stopImageSaver: return   # called from outside fn., interrupts fn.
            ij += len(images_to_concat)
            self.ij_changed.emit(ij)

            # Create csv w/ ICA networks & named ICN matches as columns
            #     NOTE: for completeness, all ICs in ICA list are included in table, 
            #              even if not mapped or in 4d Nifti
            icn_info = {}
            for ica_lookup in self.gd['ica'].keys():
                if self.stopImageSaver: break   # called from outside fn., interrupts for loop
                if ica_lookup in self.gd['mapped_ica'].keys():
                    for icn_lookup in self.gd['mapped_ica'][ica_lookup].keys():
                        if self.stopImageSaver: break   # called from outside fn., interrupts for loop
                        map_item = self.gd['mapped_ica'][ica_lookup][icn_lookup]
                        mapping_lookup = map_item.data(Qt.UserRole)
                        self.ic_changed.emit(mapping_lookup)
                        icn_custom_name = self.gd['mapped'][mapping_lookup]['icn_custom_name']
                        ica_custom_name = self.gd['mapped'][mapping_lookup]['ica_custom_name']
        
                        noise_id = 'noise' if re.match('\\.*noise', icn_lookup, flags=re.IGNORECASE) else 'ICN'
                        if icn_lookup in self.extra_items:
                            corr_r = float('inf')
                        elif ((self.corrs is not None) 
                              and (ica_lookup in self.corrs.keys())
                              and (icn_lookup in self.corrs[ica_lookup].keys())):
                            corr_r = '%0.2f' % self.corrs[ica_lookup][icn_lookup]
                        else:
                            corr_r = float('inf')
                        icn_info[ica_custom_name] = (icn_custom_name, noise_id, icn_lookup, corr_r)
            ij += 1
            self.ij_changed.emit(ij)
            self.ic_changed.emit('Exporting mappings as .csv file...')
                        
            with open(self.csvTableName, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(('ICA component:', 'ICN Label:', 'Noise Classification:', 
                                 'Template match:', 'Corr. w/ template:'))
                # lambda fn. below separates string w/ ',' then casts last part into digit if needed
                for k in sorted(icn_info.keys(), 
                                key=lambda item: (int(item.partition(',')[-1]) 
                                                         if (item[-1].isdigit() 
                                                             and ',' in item)
                                                         else float('inf'))):
                    writer.writerow((k, icn_info[k][0], icn_info[k][1], icn_info[k][2], icn_info[k][3]))
            output_files += [self.csvTableName]
            ij += 1
            self.ij_changed.emit(ij)

            # Finalities
            self.output_files = output_files # list of all output files, for outside referrence
            self.ij_finished.emit()
                

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
    def concat_images(fig_pieces, fname, cleanup=True, concat_vertical=True, recurse_call=False):
        """Concatenates saved images into single file, using PyQt5"""
        
        output_images = []
        
        if os.path.splitext(fname)[-1] != '.png':
            fname = fname + '.png'
            
        # Ensure dimensions fit within QPixMap limits
        pixmaps = []
        pixmap_widths = []
        pixmap_heights = []
        for piece in fig_pieces:
            pixmap = QPixmap(piece)
            pixmaps.append(pixmap)
            pixmap_widths.append(pixmap.size().width()) 
            pixmap_heights.append(pixmap.size().height())
        fig_pieces_select = []
        fig_pieces_leftover = []
        if concat_vertical and (sum(pixmap_heights) > 2**15): #max. pixels on any dim = 2^15
            for n in range(len(pixmap_heights)):
                if sum(pixmap_heights[0:n+1]) < 2**15:
                    fig_pieces_select.append(fig_pieces[n])
                else:
                    fig_pieces_leftover.append(fig_pieces[n])
        elif (sum(pixmap_widths) > 2**15):
            for n in range(len(pixmap_widths)):
                if sum(pixmap_widths[0:n+1]) < 2**15:
                    fig_pieces_select.append(fig_pieces[n])
                else:
                    fig_pieces_leftover.append(fig_pieces[n])
                    
        # Assemble & concatenate figs. exceeding pixmap limits
        if len(fig_pieces_leftover) > 0:
            fig_pieces = fig_pieces_select
            
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
            
            # Recursive call, for a looooong image w/ many mappings
            message = "Concatenating all displays will exceed allowed figure dimensions."
            message += " Saving output as .png files:\n"
            message += "\n   " + os.path.basename(fname) + "\n   " + os.path.basename(fname_leftover)
            message += "\n\nTo create a single figure, "
            message += "suggest removing one or more network classifications, then re-creating output"
            print(message)
            
            recursive_images = ImageSaver.concat_images(fig_pieces_leftover, fname_leftover,
                                                        cleanup=cleanup, concat_vertical=concat_vertical,
                                                        recurse_call=True)
            output_images += recursive_images

        # Assemble & concatenate figure pieces
        pixmaps = []
        pixmap_widths = []
        pixmap_heights = []
        for piece in fig_pieces:
            pixmap = QPixmap(piece)
            pixmaps.append(pixmap)
            pixmap_widths.append(pixmap.size().width()) 
            pixmap_heights.append(pixmap.size().height())
        x_start, x_end, y_start, y_end = 0, 0, 0, 0
        if concat_vertical:           # 9/3/2020 --kw-- prob. w/ vertical concat, where bottom of image blacked out. Likely work-around would be to param. to limit number of ICs plotted per figure + editable w/ zoo_OutputOpts.py
            pixCanvas = QPixmap(max(pixmap_widths), sum(pixmap_heights))
            painter = QPainter(pixCanvas)
            for n,pixmap in enumerate(pixmaps):
                painter.drawPixmap(QRectF(x_start,y_start,pixmap_widths[n],pixmap_heights[n]), 
                                   pixmap, QRectF(pixmap.rect()))
                y_start = y_start + pixmap_heights[n]
        else: # concat images horizontally
            pixCanvas = QPixmap(sum(pixmap_widths), max(pixmap_heights))
            painter = QPainter(pixCanvas)
            for n,pixmap in enumerate(pixmaps):
                painter.drawPixmap(QRectF(x_start,y_start,pixmap_widths[n],pixmap_heights[n]), 
                                   pixmap, QRectF(pixmap.rect()))
                x_start = x_start + pixmap_widths[n]
        success = painter.end()
        if success:
            success = pixCanvas.save(fname, "PNG")
            output_images += [fname]
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
        self.mapper.interrupt() #stops ongoing mapper fn.
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
