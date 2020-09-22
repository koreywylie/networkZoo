from PyQt5.QtWidgets import QDialog
import zoo_TutorialWin as tutorialwin    # PyQt widget in ../gui

class newTutorialWin(QDialog, tutorialwin.Ui_StepByStepTutorial):
    """Opens new window showing general info about Network Zoo program,
    highlighting the current step and offering tips & suggestions"""
    
    def __init__(self, **kwargs):
        
        super(self.__class__, self).__init__()
        
        newWin = QDialog(self)
        self.setupUi(newWin)
        
        # Slots for buttons
        self.buttonBox.accepted.connect(newWin.accept)
        self.buttonBox.rejected.connect(newWin.reject)
        
        loadedICA = False
        loadedICNs = False
        setMappings = False
        figsCreated = False
        
        if 'loadedICA' in kwargs.keys():
            loadedICA = kwargs['loadedICA']
        if (not loadedICA) and ('setMappings' in kwargs.keys()):
            loadedICA = kwargs['setMappings']
        if loadedICA:
            self.checkBox_ICsLoaded.setChecked(True)
            self.label_ICAstep_title.setText("1a. ICA components loaded")
            self.label_ICAstep_title.setEnabled(False)
            text = "<html><head/><body>"
            text += "<p>-To add additional ICs, click &quot;Load ICA components&quot; button or select option from under &quot;Networks&quot; menu</p>"
            text += "<p>-To remove loaded ICs, select &quot;Clear select ICA components&quot; from &quot;Networks&quot; menu</p>"
            text += "</body></html>"
            self.label_ICAstep_details.setText(text)

        if 'loadedICNs' in kwargs.keys():
            loadedICNs = kwargs['loadedICNs']
        if loadedICNs:
            self.checkBox_ICNsLoaded.setChecked(True)
            self.label_ICNstep_title.setText("1b. ICN templates loaded")
            self.label_ICNstep_title.setEnabled(False)
            text = "<html><head/><body>"
            text += "<p>-To add additional ICNs, click &quot;Load ICN templates&quot; button or select from &quot;Networks&quot; menu</p>"
            text += "<p>-To remove loaded templates, select &quot;Clear select templates&quot; from &quot;Networks&quot; menu</p>"
            text += "<p>-Non-template ICNs & noise artifacts (i.e., &quot;...nontemplateICN&quot;, &quot;...Noise_artifact&quot;) are located at the end of the list. These can be used to classify ICs without an associated template, using customized names under &quot;Possible Network Classification&quot; in the main window keft side</p>"
            text += "</body></html>"
            self.label_ICNstep_details.setText(text)

        if 'setMappings' in kwargs.keys():
            setMappings = kwargs['setMappings']
        if setMappings:
            self.checkBox_ClassificationsPresent.setChecked(True)
            self.label_Mapstep_title.setText("2. ICA comp. to ICN template classification(s) set")
            self.label_Mapstep_title.setEnabled(False)
            text = "<html><head/><body>"
            text += "<p>-To add additional classifications, select an ICA comp. &amp; ICN from respective lists, then click on &quot;Set Classification (ICA &gt; ICN)&quot; menu</p>"
            text += "<p>-Display settings can be adjusted using &quot;Display options&quot; under &quot;Edit&quot; menu</p>"
            text += "<p>-Customized names can be applied by editing text in &quot;Possible Network Classification&quot; in main window</p>"
            text += "<p>-See &quot;Classifications&quot; menu for tools to automatically identify likely classifications based on current correlations</p>"
            text += "</body></html>"
            self.label_Mapstep_details.setText(text)
        elif loadedICA and loadedICNs:
            text = "<html><head/><body>"
            text += "<p>-To display a possible classification, select an ICA comp. & ICN by clicking on respective lists</p>"
            text += "<p>-To create an ICA > ICN classification, click on &quot;Set Classification (ICA > ICN)&quot;</p>"
            text += "<p>-Display settings can be adjusted using &quot;Display options&quot; under &quot;Edit&quot; menu</p>"
            text += "<p>-Customized names can be applied by editing text in &quot;Possible Network Classification&quot; in main window left side</p>"
            text += "</body></html>"
            self.label_Mapstep_details.setText(text)
        else:
            self.label_Mapstep_title.setEnabled(False)
            self.label_Mapstep_details.setEnabled(False)

        if 'figsCreated' in kwargs.keys():
            figsCreated = kwargs['figsCreated']
        if figsCreated:
            self.checkBox_OutputGenerated.setChecked(True)
            self.label_Output_title.setText("3. Summary figure(s) & table of current classification results created")
            self.label_Output_title.setEnabled(False)
            text = "<html><head/><body>"
            text += "<p>-Figure plotting determined by current display options, adjust using &quot;Display options&quot; under &quot;Edit&quot; menu</p>"
            text += "<p>-More/fewer classifications can be plotted by adding/removing items from classifications list</p>"
            text += "<p>-Additional plotting layout options in &quot;Output parameters&quot; under &quot;Edit&quot;</p>"
            text += "<p>-Masks can be created from thresholded ICA spatial maps by selecting &quot;Create masks from classifications&quot; from &quot;Masks&quot; menu</p>"
            text += "</body></html>"
            self.label_Output_details.setText(text)
        elif loadedICA and loadedICNs and setMappings:
            text = "<html><head/><body>"
            text += "<p>-Click on &quot;Create Output Figure(s) and Table&quot;</p>"
            text += "<p>-Figure plotting determined by current display options, adjust using &quot;Display options&quot; under &quot;Edit&quot; menu</p>"
            text += "<p>-Additional plotting layout options in &quot;Output parameters&quot; under &quot;Edit&quot;</p>"
            text += "</body></html>"
            self.label_Output_details.setText(text)
        else:
            self.label_Output_title.setEnabled(False)
            self.label_Output_details.setEnabled(False)
        
        newWin.exec()