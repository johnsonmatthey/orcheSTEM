from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from app import app
import callbacks
from pages import calibration_manager, overview_manager, survey, survey_image_segmentation, cluster_manager, progress_manager,analysis_manager

#Main are the tabs running across the tap and are independent of position 
#add from here to have it formatted
MAIN_TABS = [
    {"value": "overview", "label": "Overview", "layout": overview_manager.layout},
    {"value": "calibration", "label": "Calibration", "layout": calibration_manager.layout},
]

# position based tabs that are on the left and will share same area when rendered in
POS_TABS = [
    {"value": "scan", "label": "Scan", "layout": survey.layout},
    {"value": "segment", "label": "Segment", "layout": survey_image_segmentation.layout},
    {"value": "cluster", "label": "Cluster", "layout": cluster_manager.layout},
    {"value": "progress", "label": "Progress", "layout": progress_manager.layout},
    {"value": "analysis", "label": "Analysis", "layout": analysis_manager.layout},

]
# some fixed stylings
_MAIN_PANEL_STYLE = {"padding-top": 10, "padding-left": 50, "padding-right": 50}
_MAIN_PANEL_HIDDEN_STYLE = dict(_MAIN_PANEL_STYLE, display="none")
_POS_PANEL_STYLE = {"padding-top": 10, "padding-left": 30, "padding-right": 20, "width": "100%"}
_POS_PANEL_HIDDEN_STYLE = dict(_POS_PANEL_STYLE, display="none")
_TABS_ACTIVE_STYLE = {"opacity": 1}
_TABS_DIMMED_STYLE = {"opacity": 0.4}


def main_panel_id(value):
    return f"main-panel-{value}"
def pos_panel_id(value):
    return f"pos-panel-{value}"


def navbar():
    return (
        dbc.Navbar(
            dbc.Container(
                [
                    dbc.Row(
                        children=[
                            dbc.Col(
                                [
                                    dmc.Group(
                                        [
                                            dmc.Text(
                                                "orcheSTEM",
                                                c="white",
                                                style={"font-size": 25},
                                            ),
                                        ]
                                    ),
                                ]
                            )
                        ],
                        align="center",
                        className="g-0",
                    ),
                ],
                fluid=True,
            ),
            color="#1E22AA",
            sticky="top",
            style={"shadow": "0px 1px 0px 3px"},
        )
    )


def page_tabs():
    main_tabs = dmc.Tabs(
        id="tab-main-display",
        value=MAIN_TABS[0]["value"],
        variant="outline",
        children=[
            dmc.TabsList(
                grow=True,
                children=[dmc.TabsTab(tab["label"], value=tab["value"]) for tab in MAIN_TABS],
            ),
            *[
                dmc.TabsPanel(
                    tab["layout"](),
                    value=tab["value"],
                    id=main_panel_id(tab["value"]),
                    style=_MAIN_PANEL_STYLE,
                )
                for tab in MAIN_TABS
            ],
        ],
        # Use the tab.css as only way to get the nice matching outline colour
        classNames={
            "root": "blue-outline-tabs",
            "list": "blue-outline-tabs-list",
            "tab": "blue-outline-tabs-tab",
        },    
        styles={
                "tab": {
                    "fontSize": "20px",
                },
            },
    )

    position_tabs = dmc.Tabs(
        id="tab-pos-display",
        # value=POS_TABS[0]["value"],
        variant="outline",
        orientation="vertical",
        children=[
            dmc.TabsList(
                style={"minWidth": "180px", "width": "100%"},
                children=[dmc.TabsTab(tab["label"], value=tab["value"]) for tab in POS_TABS],
            ),
        ],
        classNames={
            "root": "blue-outline-tabs",
            "list": "blue-outline-tabs-list",
            "tab": "blue-outline-tabs-tab",
        },    
        styles={
                "list": {
                    "gap": "16px",
                },
                "tab": {
                    "fontSize": "26px",
                    "padding": "12px 18px",
                },
            },
    )

    position_content = html.Div(
        [
            html.Div(
                tab["layout"](),
                id=pos_panel_id(tab["value"]),
                style=_POS_PANEL_HIDDEN_STYLE,
            )
            for tab in POS_TABS
        ]
    )

    return dmc.Paper(
        [
            html.Div(
                [
                    # dmc.Space(h=40),
                    # dmc.Center(dmc.Text("Position", fw=700, c="dimmed", size="sm", mb="sm")),
                    position_tabs,
                ],
                style={
                    "width": "220px",
                    "minWidth": "220px",
                    "padding": "57px 0px 0px 0px", # pixel perfect!

                    # "borderRight": "1px solid #dee2e6",
                },
            ),
            html.Div(
                [
                    main_tabs,
                    position_content,
                ],
                style={"flex": "1", "minWidth": 0, "padding": "16px 16px 16px 0px"},
            ),
        ],
        withBorder=True,
        radius="md",
        style={"display": "flex", "alignItems": "stretch"},
    )


def layout():
    return dmc.MantineProvider(
        html.Div(
            children=[
                dcc.Store(id="active-section", data="main"),
                navbar(),
                page_tabs(),
                dcc.Location(id='url-home'),    

                # storage of global variables
                dcc.Store(id='storage-folder-path'),
                dcc.Store(id='stage-index-active', data=0),      
                dcc.Store(id='experiment-state')        

            ]
        )
    )


app.layout = layout


# Callbacks to swap between the position or main tab display
@callback(
    Output("active-section", "data", allow_duplicate=True),
    Output("tab-main-display", "value", allow_duplicate=True),
    Input("tab-pos-display", "value"),
    prevent_initial_call=True,
)
def activate_position(pos_value):
    # None means it was just deselected by activate_main callback so do nothing to prevent looping
    if pos_value is None:
        raise PreventUpdate
    # deselect the main tab via returning None so it's no longer displayed
    return "pos", None

@callback(
    Output("active-section", "data", allow_duplicate=True),
    Output("tab-pos-display", "value", allow_duplicate=True),
    Input("tab-main-display", "value"),
    prevent_initial_call=True,
)
def activate_main(main_value):
    # None means it was just deselected by activate_position callback so do nothing to not loop
    if main_value is None:
        raise PreventUpdate
    # deselect the position tab via returning None so it doesn't display
    return "main", None


@callback(
    *[Output(main_panel_id(tab["value"]), "style") for tab in MAIN_TABS],
    *[Output(pos_panel_id(tab["value"]), "style") for tab in POS_TABS],
    Output("tab-main-display", "style"),
    Output("tab-pos-display", "style"),
    Input("active-section", "data"),
    Input("tab-pos-display", "value"),
)
def toggle_panels(active_section, pos_value):
    #tab-main-display's TabsList stays visible, where content is hidden if pos display is active
    # Using some fixed stylings defined earlier in index.py with tabs
    main_styles = [
        _MAIN_PANEL_STYLE if active_section == "main" else _MAIN_PANEL_HIDDEN_STYLE for _ in MAIN_TABS
    ]
    pos_styles = [
        _POS_PANEL_STYLE if (active_section == "pos" and tab["value"] == pos_value) else _POS_PANEL_HIDDEN_STYLE
        for tab in POS_TABS
    ]
    main_tabs_style = _TABS_ACTIVE_STYLE if active_section == "main" else _TABS_DIMMED_STYLE
    pos_tabs_style = _TABS_ACTIVE_STYLE if active_section == "pos" else _TABS_DIMMED_STYLE
    return *main_styles, *pos_styles, main_tabs_style, pos_tabs_style


if __name__ == "__main__":
    from pathlib import Path
    from util.logging_setup import setup_print_logging
    log_path = setup_print_logging(Path(__file__).resolve().parent / "logs")
    print(f"Logging to {log_path}")
    print("Starting app...")
    print("--> http://127.0.0.1:8000 to view the app.")
    app.run(debug=True, host='0.0.0.0', port=8000)
