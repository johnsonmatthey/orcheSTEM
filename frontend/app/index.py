from app import app
from dash import html, dcc
import dash_bootstrap_components as dbc 
import dash_mantine_components as dmc 
from pages import survey, survey_image_segmentation, cluster_manager, progress_manager, analysis_manager
import callbacks

def navbar():
    return(
        dbc.Navbar(
            dbc.Container([
                dbc.Row(
                    children= [
                        dbc.Col([
                            dmc.Group([
                                # html.Img(src='assets/JMLogo_400x400.jpg',height='70px'),
                                dmc.Text("JM & ePSIC Automation Application", c="white", style={'font-size':25}),
                            ]),
                        ])
                    ],
                    align = 'center',
                    className="g-0",
                ),
            ],fluid=True),
            color="#1E22AA",
            sticky="top",
            style={"shadow": "0px 1px 0px 3px"}
        )
    )



# structure for the tabs that are stored and showed on the screen
def page_tabs():
    tabs_list =  dmc.TabsList(
        grow=True,
        children=[
            dmc.TabsTab("Survey Image",value='survey-image'),
            dmc.TabsTab("Survey Image Segmentation",value='survey-image-segmentation'),
            dmc.TabsTab("Cluster Manager",value='cluster-manager'),
            dmc.TabsTab("Progress Checker",value='progress-checker'),
            dmc.TabsTab("Analysis Checker",value='analysis-manager'),
        ]
    )
    
    tab_contents = [
        dmc.TabsPanel(survey.layout(), value='survey-image', style={'padding-top':10, 'padding-left':50,'padding-right':50}),
        dmc.TabsPanel(survey_image_segmentation.layout(), value='survey-image-segmentation', style={'padding-top':10, 'padding-left':50,'padding-right':50}),
        dmc.TabsPanel(cluster_manager.layout(), value='cluster-manager', style={'padding-top':10, 'padding-left':50,'padding-right':50}),
        dmc.TabsPanel(progress_manager.layout(), value='progress-checker', style={'padding-top':10, 'padding-left':50,'padding-right':50}),
        dmc.TabsPanel(analysis_manager.layout(), value='analysis-manager', style={'padding-top':10, 'padding-left':50,'padding-right':50}),
    ]

    return(
        dmc.Tabs(
            id = 'tab-main-display',
            children=[
                tabs_list
            ] + tab_contents,
            value='survey-image',
            variant='default',
        )
    )

# layout for the bottom half of the screen
def user_options():
    return html.Div(
        style={
            "marginTop": "auto",      # Pushes it down if inside a flex container
            "paddingTop": "20px",    # some padding from components above
            "borderTop": "1px solid #dee2e6", 
            "width": "100%",
            "padding-left": 20,
            "padding-right": 20
        },
        children=[
            dmc.Group(
                grow=True,           # This is the secret sauce for even spacing
                align="center",      # Keeps checkboxes and buttons vertically aligned
                gap="md",            # The space between the items
                children=[
                    dmc.Button("Scan (A)", id="button-scan", fullWidth=True),
                    dmc.Button("Threshold (B)", id="button-threshold", fullWidth=True),
                    dmc.Button("Cluster (C)", id="button-cluster", fullWidth=True),
                    dmc.Button("Search (D)", id="button-search", fullWidth=True),
                    
                    # Grouping checkboxes so they share one slot of the even spacing
                    dmc.Group(
                        justify="center", 
                        gap="lg",
                        children=[
                            dmc.Checkbox(label="Paused (P)", id="check-paused"),
                            dmc.Checkbox(label="Stopped (S)", id="check-stopped"),
                        ]
                    ),
                    
                    dmc.Button("Help (0)", id="button-help", variant="outline", color="gray", fullWidth=True),
                ],
            )
        ]
    )
    
def layout():
    return(
        dmc.MantineProvider(
            html.Div(
                children=[
                    navbar(),
                    page_tabs(),
                    # experiment_controls(),
                    user_options(),
                    dcc.Location(id='url-home'),    
                    
                    # storage of global variables
                    dcc.Store(id='storage-folder-path'),
                    dcc.Store(id='stage-index-counter', data=0),      
                    dcc.Store(id='experiment-state')        
                ]
            )
        ),
    )
    
server = app.server
app.layout = layout


if __name__ == "__main__":
    print("Starting app...")
    print("--> http://127.0.0.1:8000 to view the app.")
    app.run(debug=True, host='0.0.0.0', port=8000)


















