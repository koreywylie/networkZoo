# Display Settings file for the ica_gui

mri_plots = {
    "icn":{
        "filled": True,
        "alpha": 0.6,
        "levels": 0.5,
        "colors": 'w'
    },
    "global":{
        "crosshairs": True,
        "thresh_ica_vol": 1e-06,
        "show_icn": True,
        "show_mapping_name": True,
        "show_ica_name": True,
        "show_icn_templateName": True,
        "display_text_size": 12
    }
}

time_plots = {
    "items":{
        "show_time_GIFT": True,
        "show_time_individual": False,
        "show_time_average": False,
        "show_spectrum": True,
        "show_time_group": False
    },
    "global":{
        "significance_threshold": 0.5,
        "sampling_rate": 2
    }
}