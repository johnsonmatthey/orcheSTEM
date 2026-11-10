from dash import dcc, html
import dash_mantine_components as dmc
import plotly.graph_objects as go

_STATUS_COLOURS = {
    "not_configured": "#888888",
    "ready": "#00BFFF",
    "running": "#FFD700",
    "done": "#2ECC71",
    "failed": "#E74C3C",
}

_STATUS_BADGE_COLOURS = {
    "not_configured": "gray",
    "ready": "cyan",
    "running": "yellow",
    "done": "green",
    "failed": "red",
}


def build_canvas_figure(pos_infos, selected_pos_index=None):
    """
    Black-background scatter plot of every stored position at its real stage (x, y), in nm.
    """
    xs, ys, colours, labels, hover_texts = [], [], [], [], []
    selected_xs, selected_ys = [], []
    for pos_info in pos_infos:
        sp = pos_info.get("stage_position")
        if not sp:
            continue
        x, y = sp["x"], sp["y"]
        pos_index = pos_info["pos_index"]
        status = pos_info["status"]
        xs.append(x)
        ys.append(y)
        colours.append(_STATUS_COLOURS.get(status, "#888888"))
        labels.append(str(pos_index))
        hover_texts.append(
            f"pos-{pos_index} ({status})<br>"
            f"X: {x} nm<br>"
            f"Y: {y} nm"
        )
        if selected_pos_index is not None and pos_index == selected_pos_index:
            selected_xs.append(x)
            selected_ys.append(y)

    fig = go.Figure()
    if selected_xs: # red border over current pos
        fig.add_trace(go.Scatter(
            x=selected_xs,
            y=selected_ys,
            mode="markers",
            marker=dict(
                size=24,
                color="rgba(0,0,0,0)",
                line=dict(color="red", width=5),
            ),
            hoverinfo="skip",
            showlegend=False,
        ))

    fig.add_trace(go.Scatter( # other data points in white
        x=xs,
        y=ys,
        mode="markers+text",
        marker=dict(
            size=18,
            color=colours,
            line=dict(color="white", width=1),
        ),
        text=labels,
        textposition="top center",
        textfont=dict(color="white"),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False,
    ))

    fig.update_layout(
        height=800,
        width=800,
        margin=dict(l=50, r=20, t=20, b=50),
        paper_bgcolor="black",
        plot_bgcolor="black",
        font_color="white",
        xaxis=dict(title="Stage X (nm)", color="white", gridcolor="#333333", zeroline=False),
        yaxis=dict(title="Stage Y (nm)", color="white", gridcolor="#333333", zeroline=False, scaleanchor="x", scaleratio=1),
        showlegend=False,
    )
    return fig

def build_position_rows(pos_infos):
    if not pos_infos:
        return dmc.Text(
            "No positions added yet. Move the stage to the first region you want, then click 'Add Position'.",
            c="dimmed", ta="center", size="sm",
        )

    header = dmc.Grid(align="center", gutter="xs", children=[
        dmc.GridCol(dmc.Text("Position", size="xs", fw=700, c="dimmed"), span=2),
        dmc.GridCol(dmc.Text("Status", size="xs", fw=700, c="dimmed"), span=2),
        dmc.GridCol(dmc.Text("Threshold", size="xs", fw=700, c="dimmed"), span=2),
        dmc.GridCol(dmc.Text("Acquisition", size="xs", fw=700, c="dimmed"), span=2),
        dmc.GridCol(dmc.Text("Run", size="xs", fw=700, c="dimmed"), span=1),
        dmc.GridCol(dmc.Text("Order", size="xs", fw=700, c="dimmed"), span=1),
        dmc.GridCol("", span=2),
    ])

    rows = [header, dmc.Divider()]
    for pos_info in pos_infos:
        pos_index = pos_info["pos_index"]
        status = pos_info["status"]
        rows.append(
            dmc.Grid(align="center", gutter="xs", children=[
                dmc.GridCol(dmc.Text(f"pos-{pos_index}", fw=600, size="sm"), span=2),
                dmc.GridCol(
                    dmc.Badge(
                        status.replace("_", " "),
                        id={"type": "badge-position-status", "index": pos_index},
                        color=_STATUS_BADGE_COLOURS.get(status, "gray"),
                        variant="light",
                    ),
                    span=2,
                ),
                dmc.GridCol(dmc.Text(pos_info.get("threshold_method") or "-", size="sm"), span=2),
                dmc.GridCol(dmc.Text(pos_info.get("acquisition_method") or "-", size="sm"), span=2),
                dmc.GridCol(
                    dmc.Checkbox(
                        id={"type": "checkbox-position-include", "index": pos_index},
                        checked=pos_info.get("included", True),
                    ),
                    span=1,
                ),
                dmc.GridCol(
                    dmc.Group(gap=2, children=[
                        dmc.ActionIcon("▲", id={"type": "btn-position-up", "index": pos_index}, variant="subtle", size="sm"),
                        dmc.ActionIcon("▼", id={"type": "btn-position-down", "index": pos_index}, variant="subtle", size="sm"),
                    ]),
                    span=1,
                ),
                dmc.GridCol(
                    dmc.Button("Open", id={"type": "btn-position-open", "index": pos_index}, size="xs", variant="light", fullWidth=True),
                    span=2,
                ),
            ])
        )
    return dmc.Stack(rows, gap="xs")


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

def position_controls():
    return html.Div(
        [
            dmc.Paper(withBorder=True, radius="sm", p="md", children=[
                dmc.Text("Positions", size="md", fw=500, ta="center"),
                dmc.Space(h=10),
                dmc.Button("New Position", id="button-new-position", fullWidth=True, variant="light", color="blue"),
                dmc.Space(h=10),
                html.Div(id="div-position-list"),
                dmc.Space(h=20),
                dmc.Divider(label="Run all positions", labelPosition="center"),
                dmc.Space(h=10),
                dmc.Button("Begin", id="button-begin-all", fullWidth=True, color="green", size="md"),
                dmc.Space(h=10),
                dmc.Progress(id="progress-bar-batch", value=0),
                dmc.Space(h=5),
                dmc.Text(id="text-batch-status", size="sm", ta="center", c="dimmed"),
                dcc.Interval(id="interval-check-batch-progress", disabled=True, interval=1500), # enabled only while a batch is running
            ]),
            dcc.Store(id="storage-positions-meta"),
            dcc.Store(id="storage-positions-included"), # dummy store separate so as to prevent triggereing callbacks in meta above that can cause infini loop
            dcc.Store(id="storage-positions-list-cache"), # last-rendered pos_infos, so refresh_position_list can skip a no-op rebuild
        ]
    )
            
def layout():
    return html.Div([
        dmc.Card(
            children = [
                dmc.CardSection(
                    children = [
                        dmc.Grid([
                            dmc.GridCol([
                                    dcc.Graph(
                                        id="graph-positions-overview",
                                        style={"height": "800px", "width": "800px"},
                                        config={"scrollZoom": False, "doubleClick": False,
                                                "displayModeBar": False},
                                    ),
                            ], span=5),
                            dmc.GridCol([
                                experiment_controls(),
                                dmc.Space(h=10),
                                position_controls(),
                            ], 
                            span=7, 
                            style={
                                "padding-left":20,
                                "padding-top":20,
                                "padding-right":20
                            }
                            ),         
                        ]),
                    ]
                ),
                # dcc.Store("stage-axis")
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        )
    ])
