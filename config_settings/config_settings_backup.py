# Backup default configuration settings for Network Zoo,
#   used to reset user-specified changes to config.json,
#   to original settings


default_configuration = { "output_directory": "saved_output",
                          "saved_analysis": False,
                          "output_created": False,
                          "corr_onClick": True,
                          "ica":{
                            "directory": "",
                            "template": "*",
                            "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii|\\.img)$",
                            "allow_multiclassifications": False
                          },
                          "icn":{
                            "directory": "data_templates/icn_atlases/Yeo7",
                            "template": "*",
                            "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii)$",
                            "extra_items": ["...nontemplate_ICN"],
                            "labels_file": ""
                          },
                          "noise":{
                            "directory": "data_templates/noise_confounders",
                            "template": "*",
                            "search_pattern": "([a-zA-Z0-9_\\-\\.]+)(\\.nii\\.gz|\\.nii)$",
                            "extra_items": ["...Noise_artifact"],
                            "discarded_icns": []
                          },
                          "smri_file": "data_templates/anatomical/MNI152_2009_template-withSkull.nii.gz",
                          "display":{
                            "mri_plots":{
                              "icn":{
                                "show_icn": True,
                                "filled": True,
                                "alpha": 0.6,
                                "levels": 0.5,
                                "colors": "w"
                              },
                              "ica":{
                                "thresh_ica_vol": False,
                                "ica_vol_thresh": 1e-06 
                              },
                              "anat":{
                                "file": False
                              },
                              "global":{
                                "display_mode": "ortho",
                                "grid_layout": False,
                                "num_rows": 1,
                                "num_cols": 5,
                                "crosshairs": True,
                                "show_colorbar": True,
                                "show_LR_annotations": True,
                                "show_mapping_name": True,
                                "show_ica_name": True,
                                "show_icn_name": True,
                                "display_text_size": 12
                              }
                            },
                            "time_plots" : {
                              "items":{
                                "show_time_series": True,
                                "show_spectrum": True,
                              },
                              "global":{
                                "sampling_rate": 2
                              }
                            }
                          },
                          "output":{
                              "create_figure": True,
                              "concat_vertical": True,
                              "figure_rows":15,
                              "figure_cols":3,
                              "create_table": True
                          },
                          "masks":{
                              "mask_dtype": "np.bool_",
                              "thresh_percentile": True,
                              "thresh_max": True,
                              "smooth_mask": True,
                              "cutoff_percentile": 99.,
                              "cutoff_fractMax": 0.33
                          }
                        }
