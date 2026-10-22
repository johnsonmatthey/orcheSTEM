from dash import dcc, html
import dash_mantine_components as dmc

# Maps each feature to the controller categories and allowed values that enable it.
FEATURE_REQUIREMENTS = {
    "Autofocus": {"lenses": ["pyjem"]},
    "Beam Blank": {"lenses": ["pyjem"]},
    "Drift Correct": {"stage": ["gatan", "pyjem"]},
    "Piezo Control": {"stage": ["pyjem"]},
    "Custom Scan": {"imaging": ["gatan", "pyjem", "qd_scanengine"]},
}
# row 0 -> stage,  row 1 -> lenses,  row 2 -> imaging
# Make sure the names match those in Feature Requirements as will be used to assign id
FEATURE_ROWS = {
    'stage': ["Drift Correct", "Piezo Control"],
    'lenses': ["Autofocus", "Beam Blank"],
    'imaging': ["Custom Scan"],
}

_FEATURE_BOX_STYLE = {
    "padding": "8px 14px",
    "borderRadius": 4,
    "color": "black",
    "fontSize": 12,
    "textAlign": "center",
    "flex": "1",
    "fontWeight": "bold"
}

def experiment_controls():
    return html.Div(
        # style={
        #     "padding": "20px 0",
        #     "padding-left":20,
        # },
        children=[
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="md",
                style={"overflow": "hidden"},
                children = [
                    dmc.Group(
                        align="center",
                        gap="md",
                        wrap="nowrap",
                        children=[
                            dmc.Text("Enter experiment name/number:", size="md", fw=500),
                            
                            dmc.TextInput(
                                id="text-input-experiment-name", 
                                value="test",
                                persistence=True,
                                style={"flex": "1"},
                                size="md"
                            ),
                            
                            dmc.Button(
                                "Create experiment", 
                                id='button-create-experiment',
                                variant="light",
                                size="md",
                            )
                        ]
                    )
                ]
            )
        ]
    )

def advanced_control_settings():
    return html.Div(
        # style={
        #     "padding": "20px 0",
        #     "padding-left":20
        # },
        children=[
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="md",
                style={"overflow": "hidden"},
                children=[
                    dmc.Button("Advanced Control Settings", id="button-advanced-settings", variant="outline", size="md", fullWidth=True, c="dimmed"),
                    dmc.Space(h=10),
                    dmc.Collapse([
                        dmc.Grid(align="flex-end", gutter="sm", children=[
                            # Stage control row
                            dmc.GridCol([
                                dmc.Text("Stage control method", size="sm"),
                                dmc.Select(id="dropdown-control-stage", data=[]),
                            ], span=4),
                            dmc.GridCol([
                                dmc.Text("Feature availability", size="sm", fw=500),
                                dmc.Group(gap="sm", children=[
                                    *[
                                        html.Div(id=f"feature-status-{feature.lower().replace(' ', '-')}", children=feature, style=_FEATURE_BOX_STYLE)
                                        for feature in FEATURE_ROWS['stage']
                                    ],
                                    # html.Div(id="feature-status-drift-correct", children="Drift Correct", style=_FEATURE_BOX_STYLE),
                                    # html.Div(id="feature-status-piezo-control", children="Piezo Control", style=_FEATURE_BOX_STYLE),
                                ]),
                            ], span=8),

                            # Lenses control row
                            dmc.GridCol([
                                dmc.Text("Lenses control method", size="sm"),
                                dmc.Select(id="dropdown-control-lenses", data=[]),
                            ], span=4),
                            dmc.GridCol([
                                dmc.Group(gap="sm", children=[
                                    *[
                                        html.Div(id=f"feature-status-{feature.lower().replace(' ', '-')}", children=feature, style=_FEATURE_BOX_STYLE)
                                        for feature in FEATURE_ROWS['lenses']
                                    ],
                                ]),
                            ], span=8),

                            # Imaging control row
                            dmc.GridCol([
                                dmc.Text("Imaging method", size="sm"),
                                dmc.Select(id="dropdown-control-imaging", data=[]),
                            ], span=4),
                            dmc.GridCol([
                                dmc.Group(gap="sm", children=[
                                    *[
                                        html.Div(id=f"feature-status-{feature.lower().replace(' ', '-')}", children=feature, style=_FEATURE_BOX_STYLE)
                                        for feature in FEATURE_ROWS['imaging']
                                    ],
                                ]),
                            ], span=8),
                        ]),
                    ], id="collapse-advanced-settings")
                ]
            )
        ]
    )

def survey_image_config():
    return html.Div(
        children=[
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="md",
                style={"overflow": "hidden"},
                children=[
                    dmc.Text("Survey Image Settings", size="md", fw=500, ta="center",),
                    dmc.Space(h=10),
                    dmc.Group([
                        dmc.NumberInput(
                            id="input-survey-image-size", label="Survey Image Size (px)", 
                            value=512, min=256, step=256, 
                            allowNegative=False, allowDecimal=False, thousandSeparator=","
                            ),

                        dmc.NumberInput(
                            id="input-survey-dwell-time", label="Survey Dwell Time (us)", 
                            value=15, min=1, step=1, 
                            stepHoldDelay=500, stepHoldInterval=100, allowNegative=False, allowDecimal=False, thousandSeparator=","
                            ),
                        dmc.NumberInput(
                            id="input-survey-flyback-time", label="Survey Flyback Time (us)", 
                            value=100, min=1, step=1, 
                            stepHoldDelay=500, stepHoldInterval=100, allowNegative=False, allowDecimal=False, thousandSeparator=","
                            ),

                    ], grow=True),
                ]
            )
        ]
    )

def make_radiocard(label, additional_components):
    return dmc.RadioCard(
        withBorder=True,
        p="sm",
        className="checkboxcard-root",
        value=label,
        style={"height": 120, "display": "flex", "flexDirection": "column", "justifyContent": "flex-start"},
        children=[
            dmc.Group([
                dmc.RadioIndicator(),
                dmc.Box([
                    dmc.Text(label, lh="1.3", fz="sm", fw="bold"),
                ]),
            ], wrap="nowrap", align="flex-start",),
            dmc.Space(h=10),
            *additional_components
        ]
    )


def drift_correction_config():
    return html.Div(
        children=[
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="md",
                style={"overflow": "hidden"},
                children=[   
                    dmc.Text("Drift Correction Settings", size="md", fw=500, ta="center",),
                    
                    dmc.Space(h=10),         
                    dmc.Grid(align="flex-end", gutter="sm", children=[
                        dmc.GridCol([
                            # dmc.Text("Stage control method", size="sm"),
                            dmc.Image(
                                id="image-survey-driftregion",
                                src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/images/bg-4.png",
                                h=290,
                                fit="contain"),
                        ], span=6),


                        dmc.GridCol([

                            dmc.Group([
                                dmc.NumberInput(
                                    id="input-drift-dwell-time", label="Dwell Time (us)", 
                                    value=50, min=1, step=1, 
                                    stepHoldDelay=500, stepHoldInterval=100,allowNegative=False, allowDecimal=False, thousandSeparator=","
                                    ),
                                dmc.NumberInput(
                                    id="input-drift-flyback-time", label="Flyback Time (us)", 
                                    value=150, min=1, step=1, 
                                    stepHoldDelay=500, stepHoldInterval=100,allowNegative=False, allowDecimal=False, thousandSeparator=","
                                    ),
                            ], grow=True),

                            # TODO grab this setting from the backend config for max!
                                
                            dmc.Space(h=10),

                            dmc.Box([
                                dmc.RadioGroup(
                                    id="radiocard-group-drift-correction-method",
                                    deselectable=False,
                                    value="Full Search",
                                    children=[
                                        dmc.Group(
                                            gap="sm",
                                            grow=True,
                                            children=[
                                                make_radiocard(
                                                    "Full Search", 
                                                    []
                                                ),
                                                make_radiocard(
                                                    "Box Region", 
                                                    [
                                                        dmc.NumberInput(
                                                            id="input-drift-region-size", 
                                                            label = r"Size / px",
                                                            value=128, min=16, step=16, 
                                                            #size="sm",
                                                            allowNegative=False, allowDecimal=False,
                                                            stepHoldDelay=500, stepHoldInterval=100,
                                                            debounce=500,
                                                            
                                                        ),
                                                    ]
                                                ),
                                                make_radiocard(
                                                    "Scan Region", 
                                                    []
                                                ),
                                            ],
                                        ),
                                    ]
                                ),
                            ]),
                            dcc.Store(id='storage-drift-region-box-coords'), # Store box coords here for ease later for pipeline
                            dmc.Space(h=10),
                            dmc.Button("Acquire Drift Region", id="button-acquire-drift-region", variant="outline", fullWidth=True),
                            dmc.Space(h=10),
                            dmc.Alert("Ensure drift region is acquired!", color="red"),

                        ], span=6),
                ])
                ]
            )
        ]
    )


def layout():
    return html.Div([
        dmc.Card(
            children = [
                dmc.CardSection(
                    children = [
                        html.Div(
                            style={"display": "flex", "flexDirection": "row", "alignItems": "flex-start", "width": "100%"},
                            children=[
                                html.Div(
                                    style={"flex": "0 0 auto"},
                                    children=[
                                        dcc.Graph(
                                            id="graph-survey",
                                            style={"height": "800px", "width": "800px"},
                                            config={"scrollZoom": False, "doubleClick": False,
                                                    "displayModeBar": False},
                                        ),
                                    ]
                                ),

                                # The compucentric controls panel - mantine does not support horizontal collapse so use flexbox and widths
                                html.Div(
                                    id="compucentric-panel-wrapper",
                                    style={
                                        "display": "flex",
                                        "flexDirection": "row",
                                        "width": "20px",
                                        "overflow": "hidden",
                                        "transition": "width 0.3s ease-in-out",
                                        "flexShrink": "0",
                                        "alignSelf": "stretch",
                                    },
                                    children=[
                                        # Collapse/expand toggle for compucentric controls
                                        html.Div(
                                            id="compucentric-strip-toggle",
                                            n_clicks=0,
                                            style={
                                                "width": "20px",
                                                "minWidth": "20px",
                                                "backgroundColor": "#dee2e6",
                                                "cursor": "pointer", # so you actually can tell it is clickable
                                                "display": "flex",
                                                "alignItems": "center",
                                                "justifyContent": "center",
                                                "alignSelf": "stretch",
                                            },
                                            children=[
                                                html.Span(
                                                    "Compucentric Controls",
                                                    style={
                                                        "writingMode": "vertical-rl",
                                                        "transform": "rotate(180deg)",
                                                        "fontSize": "20px",
                                                        "fontWeight": "600",
                                                        "color": "#495057",
                                                        "userSelect": "none",
                                                        "whiteSpace": "nowrap",
                                                    }
                                                )
                                            ]
                                        ),
                                        # Calibration section that expands/collapses
                                        html.Div(
                                            style={"width": "220px", "minWidth": "220px", "padding": "10px 10px 10px 10px"},
                                            children=[
                                                dmc.Grid([
                                                    dmc.GridCol([
                                                        dmc.Button("Calibrate Tilt", id="button-survey-compucentric", fullWidth=True),
                                                        dmc.Space(h=10),
                                                        dcc.Graph(
                                                            id='tilt-shift-orientation', 
                                                            figure={
                                                                "layout": {
                                                                    "height": 200,
                                                                    "width": 200,
                                                                    "xaxis": {"range": [-4, 4]},
                                                                    "yaxis": {"range": [-4, 4]},
                                                                    "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
                                                                }
                                                            }, 
                                                            responsive=False, 
                                                            style={"height": "200px", "width": "200px"},
                                                            config={ 'displayModeBar': False})
                                                    ], span=12),

                                                    dmc.GridCol([
                                                        dmc.Space(h=10),
                                                        html.H3('Compucentric Tilt', style={'textAlign': 'center', 'margin': 0}),
                                                        dmc.Space(h=10),
                                                        dmc.Grid(
                                                            columns=3, # just to make it more obviously a 3x3 layout
                                                            gutter="xs",
                                                            children=[
                                                                # Top
                                                                dmc.GridCol(span=1),
                                                                dmc.GridCol([dmc.Button("+x", id="button-+x-compucentric", fullWidth=True)], span=1),
                                                                dmc.GridCol(span=1),
                                                                # Mid
                                                                dmc.GridCol([dmc.Button("+y", id="button-+y-compucentric", fullWidth=True)], span=1),
                                                                dmc.GridCol(span=1),
                                                                dmc.GridCol([dmc.Button("-y", id="button--y-compucentric", fullWidth=True)], span=1),
                                                                # Bottom
                                                                dmc.GridCol(span=1),
                                                                dmc.GridCol([dmc.Button("-x", id="button--x-compucentric", fullWidth=True)], span=1),
                                                                dmc.GridCol(span=1),
                                                            ]
                                                        ),
                                                        dmc.Space(h=10),
                                                        dmc.Center(html.Div(id='tilt-shift-text', children='')),
                                                    ], span=12),
                                                ],)# style={"margin-left": 10, "margin-right": 10,}),
                                            ]
                                        ),
                                    ]
                                ),

                                # Remaining experimental controls
                                html.Div(
                                    style={
                                        "flex": "1",
                                        "paddingLeft": 20,
                                        "paddingTop": 20,
                                        "paddingRight": 20,
                                        "paddingBottom": 00,
                                        "minWidth": 500,
                                    },
                                    children=[
                                        experiment_controls(),
                                        dmc.Space(h=20),
                                        advanced_control_settings(),
                                        dmc.Space(h=20),
                                        survey_image_config(),
                                        dmc.Space(h=20),
                                        drift_correction_config(),
                                        dmc.Space(h=20),
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
                dcc.Store("stage-axis")
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        )
    ])





































