from dash import html, dcc
import dash_mantine_components as dmc

def scan_progression():
    return dmc.Paper(
        withBorder=True,
        radius="sm",
        p="md",
        style={"overflow": "hidden"},

        children = [
            dmc.Grid([
                dmc.GridCol([
                    # dmc.Text("Previous Scan", size="sm", c="dimmed", ta="center"),
                    dmc.Center(dmc.Image(id="img-prev-scan", radius="md", fit="contain", w=400, h="auto"),),
                ], span=6, ),
                dmc.GridCol([
                    # dmc.Text("Current Scan", size="sm", c="dimmed", ta="center"),
                    dmc.Center(dmc.Image(id="img-current-scan", radius="md", fit="contain", w=400, h="auto",),),
                ], span=6),

            ], style = {"padding-left":0, "padding-top":0, "padding-right":0, "padding-bottom":0}),
            
            dmc.Space(h="xl"),

            dmc.Grid([
                    dmc.GridCol([
                        # dmc.Image(id="img-drift", style={"width": "100%", "height": "auto"}),
                        dmc.Text("Drift Tracker", size="sm", ta="center"),
                        dmc.Center(
                            dcc.Graph(
                            id='graph-overall-drift', 
                            figure={
                                "data": [
                                    {"type": "scatter", "x": [], "y": [], "mode": "markers", "marker": {"color": "black", "size": 8}, "hoverinfo": "skip", "showlegend": False},
                                    {"type": "scatter", "x": [], "y": [], "mode": "markers", "marker": {"color": "red", "size": 10}, "showlegend": False},
                                ],
                                "layout": {
                                    "height": 400,
                                    "width": 400,
                                    "margin": {"l": 20, "r": 20, "t": 0, "b": 20},
                                    "xaxis": {"visible": True, "autorange": False, "fixedrange": True, "range": [-256, 256]},
                                    "yaxis": {"visible": True, "autorange": False, "fixedrange": True, "range": [-256, 256]},
                                }
                            }, 
                            responsive=False, 
                            style={"height": "400px", "width": "400px"},
                            # config={ 'displayModeBar': False}
                            )
                        ),
                    ], span = 6, style = {"padding-left":0, "padding-top":0, "padding-right":0, "padding-bottom":0}),
                    # dmc.Paper(
                    #     withBorder=True, p='xs', radius='sm',
                    #     children = [
                    #         dmc.Text("Drift (X, Y)", size="sm", c="dimmed"),
                    #         dmc.Text(id="text-drift-value", children="0.0, 0.0 px", w=700, size="lg"),
                    #         dmc.Image(id="img-drift", style={"width": "100%", "height": "auto"})
                    #     ]
                    # ),
                    dmc.GridCol([
                        dmc.Paper(
                            withBorder=True, p='xs', radius='sm',
                            children = [
                                dmc.Text("Active particle", size="xs", c="dimmed"),
                                dmc.Text(id="text-particle-count", children="ID: #000", w=700, size="lg")
                            ]
                        ),
                    ], span=6),

                ]  
            ),         
        ],   
    )




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
                                    id="graph-survey-progress",
                                    style={"height": "800px", "width": "800px"},
                                ),

                                dmc.Text(id="progress-bar-label",size="xs", c="dimmed", mb=5, style={"margin":"10px 10px 0px 10px"}),
                                html.Progress(
                                    id = "progress-bar-section",
                                    value="0",
                                    max="100",
                                    style={"width":"100%", "height":"20px", "margin" :"0px 10px 10px 10px"} # margin is of format {top, right, bottom, left}
                                )

                            ], span=5),
                            
                            dmc.GridCol([
                                scan_progression()                              
                            ], span=7,
                            style = {
                                "padding-left":20,
                                "padding-top":20,
                                "padding-right":20
                            }
                            ),
                        ])                        
                    ]
                )
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        ),
        dcc.Interval(id='interval-check-progress', disabled=False, interval=1000), # will change this to a proper button system later
        dcc.Store("storage-state-pipeline")
    ])















