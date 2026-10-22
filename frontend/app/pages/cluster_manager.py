from dash import html, dcc 
import dash_mantine_components as dmc

def layout():
    return html.Div([
        dmc.Card(
            children = [
                dmc.CardSection(
                    style={"overflow": "visible"},
                    children = [
                        dmc.Grid([
                            dmc.GridCol([
                                dcc.Graph(
                                    id='graph-survey-image-clustering',
                                    # Enable the rectangle drawing tool by default
                                    config={
                                        "modeBarButtonsToAdd": ["drawrect", "eraseshape"],
                                        "displayModeBar": True, 
                                        # "scrollZoom": True
                                    },
                                    style={"height": "800px", "width": "800px"},
                                ),
                            ], span=5),
                            dmc.GridCol([
                                dmc.Stack([
                                    dmc.Slider(
                                        id="slider-clustering",
                                        value=50,
                                        marks=[
                                            {"value": 20, "label": "20%"},
                                            {"value": 50, "label": "50%"},
                                            {"value": 80, "label": "80%"},
                                        ],
                                        mb=35,
                                    ),
                                    
                                    dmc.Divider(label="Region Management", labelPosition="center"),
                                    dmc.Group([
                                        dmc.Button("Reset to Watershed", id="btn-reset-boxes", variant="outline", color="red"),
                                    ], grow=True),
                                    
                                    dmc.Divider(label="Search Pipeline Configuration", labelPosition="center"),
                                    dmc.Group([
                                        dmc.NumberInput(id="input-sampling", label="Sampling Res", value=128, min=32, step=32),
                                        dmc.NumberInput(id="input-focus-freq", label="Focus (every N)", value=1),
                                        dmc.NumberInput(id="input-drift-freq", label="Drift (every N)", value=1),
                                    ], grow=True),
                                    dmc.Group([
                                        # dmc.NumberInput(id="input-survey-image-size", label="Survey Image Size", value=512),
                                        dmc.NumberInput(id="input-full-image-size", label="Full Image Size", value=4096, min=512, step=512),
                                    ], grow=True),
                                    dmc.Space(h=10),
                                    dmc.Alert("Ensure experiment is created and clustered before searching.", color="blue"),
                                    dmc.Space(h=10),

                                    dmc.Grid([
                                        dmc.GridCol([
                                            dmc.Checkbox(id="checkbox-enable-4dstem", label="Acquire 4D-STEM?", size="md", persistence=True),
                                            dmc.Space(h=10),

                                            dmc.Collapse([
                                                dmc.Text("Choose method to control the 4D-STEM detector during acquisition.", size="sm"),
                                                dmc.Select(
                                                    id="dropdown-control-4dstem-detector",
                                                    data = [],
                                                ),
                                                dmc.Space(h=10),
                                                dmc.TextInput(id="input-4dstem-savepath", label="Save Path", value="X:/save/path/", persistence=True),
                                                dmc.Group([
                                                    dmc.NumberInput(
                                                        id="input-4dstem-dwell-time", label="Dwell Time (us)", 
                                                        value=1000, min=1, step=1,
                                                        stepHoldDelay=500, stepHoldInterval=100,allowNegative=False, allowDecimal=False, thousandSeparator=","
                                                    ),
                                                    dmc.NumberInput(
                                                        id="input-4dstem-flyback-time", label="Flyback Time (us)", 
                                                        value=10000, min=1, step=1,
                                                        stepHoldDelay=500, stepHoldInterval=100, allowNegative=False, allowDecimal=False, thousandSeparator=","
                                                        ),
                                                    dmc.NumberInput(id="input-4dstem-bitdepth", label="Bit Depth", value=6, min=1, step=1, allowNegative=False, allowDecimal=False)

                                                ], grow=True),
                                                dmc.Space(h=10),
                                                dmc.Group([
                                                    dmc.Checkbox(id="checkbox-enable-autoptych", label="Auto Ptych?", size="md", persistence=True),
                                                    dmc.NumberInput(id="input-autoptych-slices", label="Slices", value=3, min=1, step=1, persistence=True),
                                                    dmc.NumberInput(id="input-autoptych-slice-thick", label="Thickness /nm ", value=3, min=1, step=1, persistence=True),
                                                ], grow=True)
                                            ], id="collapse-4dstem-options", opened=True)
                                        ], span=6),
                                        
                                        # SI options
                                        dmc.GridCol([
                                            dmc.Checkbox(id="checkbox-enable-si", label="Acquire SI?", size="md", persistence=True),
                                            dmc.Space(h=10),
                                            dmc.Collapse([
                                                dmc.Text("Choose method to control the SI detector during acquisition.", size="sm"),
                                                dmc.Select(
                                                    id="dropdown-control-si-detector",
                                                    data = [],
                                                ),
                                                dmc.Space(h=10),
                                                # dmc.TextInput(id="input-si-savepath", label="Save Path", value="X:/save/path/", persistence=True),
                                                dmc.Group([
                                                    dmc.Checkbox(id="checkbox-enable-si-eels", label="Acquire EELS?", size="md", checked = True, persistence=True),
                                                    dmc.Checkbox(id="checkbox-enable-si-eds", label="Acquire EDS?", size="md", checked = True, persistence=True),
                                                    dmc.Checkbox(id="checkbox-enable-si-custom", label="Custom Scan?", size="md", checked = True, persistence=True),

                                                ], style={"paddingTop": "28px"}),
                                                dmc.Space(h=10),

                                                dmc.Group([
                                                    dmc.NumberInput(
                                                        id="input-si-dwell-time", label="Dwell Time (us)", 
                                                        value=1000, min=1, step=1,
                                                        stepHoldDelay=500, stepHoldInterval=100,allowNegative=False, allowDecimal=False, thousandSeparator=","
                                                    ),
                                                    dmc.NumberInput(
                                                        id="input-si-flyback-time", label="Flyback Time (us)", 
                                                        value=10000, min=1, step=1,
                                                        stepHoldDelay=500, stepHoldInterval=100, allowNegative=False, allowDecimal=False, thousandSeparator=","
                                                        ),
                                                ], grow=True),

                                                dmc.Space(h=10),

                                                dmc.Group([
                                                    dmc.Checkbox(id="checkbox-enable-autoSI", label="Auto Analysis?", size="md", persistence=True),
                                                    dmc.NumberInput(id="input-si-subscan", label="Subscan", value=1, min=1, step=1, allowNegative=False, allowDecimal=False),
                                                    dmc.NumberInput(id="input-si-passes", label="Num passes", value=1, min=1, step=1, allowNegative=False, allowDecimal=False),
                                                ], grow=True),
                                            ], id="collapse-si-options", opened=True)


                                        ], span=6),


                                    ]),
                                
                                
                                ])
                            ], span=7)
                        ]),
                    ]
                )
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        ),
        dcc.Store(id="storage-bounding-boxes"),
        dcc.Store(id="storage-original-boxes")
    ])
