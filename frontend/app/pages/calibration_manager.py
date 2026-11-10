from dash import dcc, html
import dash_mantine_components as dmc


# def experiment_controls():
#     return html.Div(
#         # style={
#         #     "padding": "20px 0",
#         #     "padding-left":20,
#         # },
#         children=[
#             dmc.Paper(
#                 withBorder=True,
#                 radius="sm",
#                 p="md",
#                 style={"overflow": "hidden"},
#                 children = [
#                     dmc.Group(
#                         align="center",
#                         gap="md",
#                         wrap="nowrap",
#                         children=[
#                             dmc.Text("Enter experiment name/number:", size="md", fw=500),
                            
#                             dmc.TextInput(
#                                 id="text-input-experiment-name", 
#                                 value="test",
#                                 persistence=True,
#                                 style={"flex": "1"},
#                                 size="md"
#                             ),
                            
#                             dmc.Button(
#                                 "Create experiment", 
#                                 id='button-create-experiment',
#                                 variant="light",
#                                 size="md",
#                             )
#                         ]
#                     )
#                 ]
#             )
#         ]
#     )


def build_connection_status(session):
    """The active instrument and holder, then one row per device showing whether its connection succeeded."""
    label = next((i["label"] for i in session["instruments"] if i["value"] == session["instrument"]), session["instrument"])
    rows = [dmc.Text(f"Active: {label}  |  holder: {session['holder'] or '-'}", fw=500)]
    for connection in session["connections"]:
        ok = connection["connected"]
        rows.append(
            dmc.Group(gap="sm", children=[
                dmc.Badge("Connected" if ok else "Not connected", color="green" if ok else "red", variant="light", w=130),
                dmc.Text(connection["label"], fw=600, size="sm", w=110),
                dmc.Text(connection["message"], size="sm", c="dimmed"),
            ])
        )
    if not session["connections"]:
        rows.append(dmc.Text("This instrument declares no hardware connections.", size="sm", c="dimmed"))
    return dmc.Stack(rows, gap="xs")


def layout():
    return html.Div([
        dmc.Card(
            children = [
                dmc.CardSection(
                    children = [
                        dmc.Stack(p="md", gap="sm", children=[
                            dmc.Text("Instrument and sample holder", fw=600),
                            dmc.Group(align="flex-end", gap="md", children=[
                                dmc.Select(id="dropdown-instrument", label="Instrument", data=[], allowDeselect=False, w=340),
                                dmc.Select(id="dropdown-holder", label="Holder", data=[], allowDeselect=False, w=220),
                                dmc.Button("Connect", id="button-calibration-connect", variant="light"),
                            ]),
                            dcc.Loading(html.Div(id="div-connection-status"), type="circle"),
                            dcc.Store(id="store-microscope-session"),
                        ]),

                        #     style={
                        #         "display": "flex",
                        #         "flexDirection": "row",
                        #         "alignItems": "flex-start",
                        #         "gap": "20px",
                        #         "width": "100%",
                        #         "overflowX": "auto",
                        #         "padding": "8px",
                        #         "boxSizing": "border-box",
                        #     },
                        #     children=[
                        #         html.Div(
                        #             style={
                        #                 "flex": "0 0 800px",
                        #                 "width": "800px",
                        #             },
                        #             children=[
                        #                 dcc.Graph(
                        #                     id="graph-overview",
                        #                     style={"height": "800px", "width": "800px"},
                        #                     config={"scrollZoom": False, "doubleClick": False,
                        #                             "displayModeBar": False},
                        #                 ),
                        #             ],
                        #         ),
                        #         html.Div(
                        #             style={
                        #                 "flex": "1 1 auto",
                        #                 "minWidth": "420px",
                        #             },
                        #             children=[
                        #                 experiment_controls(),
                        #                 dmc.Space(h=20),
                        #             ],
                        #         ),
                        #     ],
                        # ),
                    ]
                ),
                # dcc.Store("stage-axis")
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        )
    ])

