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
                                    id="graph-analysis-progress",
                                    style={"height": "800px", "width": "800px"},
                                ),

                                dmc.Text(id="progress-bar-analysis-label",size="xs", c="dimmed", mb=5),
                                html.Progress(
                                    id = "progress-bar-analysis",
                                    value="0",
                                    max="100",
                                    style={"width":"100%", "height":"20px"}
                                )

                            ], span=6),
                            
                            dmc.GridCol([
                                # dmc.Grid([
                                #     dmc.GridCol([
                                #         dmc.Text("Previous Scan", size="xs", c="dimmed", ta="center"),
                                #         dmc.Image(id="img-prev-scan", radius="md", fit="contain"),
                                #     ], span=6),
                                #     dmc.GridCol([
                                #         dmc.Text("Current Scan", size="xs", c="dimmed", ta="center"),
                                #         dmc.Image(id="img-current-scan", radius="md", fit="contain"),
                                #     ], span=6),

                                # ]),
                                
                                # dmc.Space(h="xl"),

                                # dmc.SimpleGrid(
                                #     cols=2,
                                #     children = [
                                #         dmc.Paper(
                                #             withBorder=True, p='xs', radius='sm',
                                #             children = [
                                #                 dmc.Text("Drift (X, Y)", size="xs", c="dimmed"),
                                #                 dmc.Text(id="text-drift-value", children="0.0, 0.0 px", w=700, size="lg")
                                #             ]
                                #         ),
                                #         dmc.Paper(
                                #             withBorder=True, p='xs', radius='sm',
                                #             children = [
                                #                 dmc.Text("Active particle", size="xs", c="dimmed"),
                                #                 dmc.Text(id="text-particle-count", children="ID: #000", w=700, size="lg")
                                #             ]
                                #         ),
                                #     ]  
                                # ),
                            
                            
                            ], span=6),                            
                        ])                        
                    ]
                )
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        ),
        dcc.Interval(id='interval-check-analysis-progress', disabled=False, interval=1000), # will change this to a proper button system later
        dcc.Store(id="storage-state-analysis")
    ])















