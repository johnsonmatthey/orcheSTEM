from dash import html
import dash_mantine_components as dmc
import numpy as np

def _classical_controls():
    return dmc.Stack([
        dmc.Text("Median Filter Size"),
        dmc.Slider(
            id="slider-median-filter-classical",
            min=1, max=15, step=2, value=1,
            marks=[{"value": i, "label": str(i)} for i in range(1, 16, 2)]
        ),
        dmc.Space(h=10),
    ], gap="sm")

def _ml_controls():
    return dmc.Grid(gutter="sm", children=[
            dmc.GridCol(dmc.TextInput(id="input-ml-model-ip", label="IP", placeholder="127.0.0.1", value="127.0.0.1"), span=8),
            dmc.GridCol(dmc.NumberInput(id="input-ml-port", label="Port", value=8090, min=0, max=65535, step=1), span=4),
            dmc.GridCol(dmc.Button(id="button-apply-ml", children="Apply ML Segmentation", fullWidth=True, color="indigo", size="md"), span=12),
            # dmc.GridCol(dmc.TextInput(id="input-ml-param-a", label="Extra Param A", placeholder="Enter value..."), span=6),
            # dmc.GridCol(dmc.TextInput(id="input-ml-param-b", label="Extra Param B", placeholder="Enter value..."), span=6),
        ]),
        
def _threshold_controls(min_thresh=0, max_thresh=255, steps=25):
    markers = [{"value": i, "label": str(i)} for i in range(min_thresh, max_thresh+1, steps)]
    return dmc.Stack([
        dmc.Text("Median Filter Size"),
        dmc.Slider(
            id="slider-median-filter-threshold",
            min=1, max=15, step=2, value=1,
            marks=[{"value": i, "label": str(i)} for i in range(1, 16, 2)]
        ),
        dmc.Space(h=10),
        dmc.Text("Set intensity range for thresholding:"),
        dmc.RangeSlider(
            id="range-slider-threshold",
            value=[150, 255],
            min=min_thresh,
            max=max_thresh,
            marks=markers,
            mb=35,
        ),
    ], gap="sm"),

def _thin_feature_controls():
    markers_area = [{"value": i, "label": str(i)} for i in np.arange(0, 1000+1, 200)]
    markers_area[0] = {"value": 1, "label": str(1)}
    markers_ratio = [{"value": i, "label": str(i)} for i in np.arange(1, 10+1, 1)]
    return dmc.Stack([
        dmc.Space(h=10),
        dmc.Group([
            dmc.GridCol([
                dmc.Text("Smoothing method", size="sm"),
                dmc.Select(id="dropdown-smoothing", data=['none', 'gaussian', 'median'], value='none'),
            ], span=4),
            dmc.NumberInput(
                id="input-smoothing", label="Sigma for smoothing", 
                value=1.0, min=0.1, step=0.1, 
                allowNegative=False, allowDecimal=True, thousandSeparator=","
                ),
        ], grow=True),
        dmc.Group([
            dmc.GridCol([
                    dmc.Text("Background subtraction", size="sm"),
                    dmc.Select(id="dropdown-background", data=['none', 'large_gaussian', 'rolling_ball'], value='none'),
                ], span=4),
                    dmc.NumberInput(
                id="input-background", label="Sigma for background", 
                value=20, min=2, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
        ], grow=True),
        dmc.RadioGroup(
            children=dmc.Group([dmc.Radio(k, value=k) for k in ['bright','dark']], my=10),
            id="polarity-selector",
            value='bright',
            label="Select polarity",
            size="sm",
            mb=10,
        ),
        dmc.Group([
            dmc.GridCol([
                    dmc.Text("Segmentaion/thresholding method", size="sm"),
                    dmc.Select(id="dropdown-segmentation", data=['adaptive', 'global', 'hysteresis'], value='adaptive'),
                ], span=4),
                dmc.GridCol([
                    dmc.Text("For adaptive these are the neighbourhood size & offset and for global & hystersis they are intensity percentages", size="sm"),
                    dmc.NumberInput(
                id="input-threshold-value", label="Value for threshold", 
                value=35, min=2, step=1, 
                allowNegative=False, allowDecimal=True, thousandSeparator=","
                ),
                    dmc.NumberInput(
                id="input-threshold-sigma", label="Sigma for threshold", 
                value=0, min=0, step=1, 
                allowNegative=False, allowDecimal=True, thousandSeparator=","
                ),
                ], span=7),
        ], grow=True),
        dmc.Group([
        dmc.GridCol([
                    dmc.Text("Watershed method", size="sm"),
                    dmc.Select(id="dropdown-watershed", data=['none', 'flooding', 'topological', 'spanning_forests'], value='none'),
            ], span=4),
            dmc.NumberInput(
                id="input-watershed-distance", label="Minimum distance for topological watershed", 
                value=10, min=0, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
        ], grow=True),
        dmc.Group([
            dmc.Text("Simple Clean up", size="sm"),
            dmc.NumberInput(
                id="input-min-open", label="Minimum size for morphological opening", 
                value=1, min=1, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
            dmc.NumberInput(
                id="input-min-close", label="Minimum size for morphological closing", 
                value=2, min=1, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
            dmc.NumberInput(
                id="input-min-object", label="Minimum object size for removal", 
                value=10, min=1, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
            dmc.NumberInput(
                id="input-min-hole", label="Minimum hole size for removal", 
                value=10, min=1, step=1, 
                allowNegative=False, allowDecimal=False, thousandSeparator=","
                ),
        ], grow=True),
        dmc.Group([
            dmc.Text("Post-process", size="sm"),
            dmc.RangeSlider(
                id="Area-size-selector", label="Selection by pixel area", 
                value=[150, 255],
                min=10,
                max=1000,
                marks=markers_area,
                mb=35,
            ),
            dmc.Space(h=10),
            dmc.RangeSlider(
                id="hw-ratio-selector", label="Selection by height/width ratio",
                value=[1, 2],
                min=0.1,
                max=10,
                marks=markers_ratio,
                mb=35,
            ),
        ], grow=True),
    ], gap="sm")

_SEGMENTATION_METHODS = {
    'Classical': {
        "description": "Traditional image processing-based segmentation using filters and thresholding.",
        "method_id": "segment-block-classical",
        "endpoint": "segment-classical",
        "triggers": {"slider-median-filter-classical"},
        "controls": _classical_controls,
    },
    'ML': {
        "description": "Machine Learning-based segmentation using a pre-trained model.",
        "method_id": "segment-block-ml",
        "endpoint": "segment-ml",
        "triggers": {"button-apply-ml"},#, "input-ml-model-ip", "input-ml-port"},
        "controls": _ml_controls,
    },
    'Thresholding': {
        "description": "Simple intensity-based segmentation using a user-defined threshold.",
        "method_id": "segment-block-threshold",
        "endpoint": "segment-thresholding",
        "triggers": {"slider-median-filter-threshold", "range-slider-threshold"},
        "controls": _threshold_controls,
    },
            'Thin Features': {
        "description": "Multi-step method for isolating thin features.",
        "method_id": "segment-block-thin",
        "endpoint": "segment-thin-feature",
        "triggers": {
            "dropdown-smoothing",
            "input-smoothing",
            "dropdown-background",
            "input-background",
            "polarity-selector",
            "dropdown-segmentation", 
            "input-threshold-value", 
            "input-threshold-sigma",
            "dropdown-watershed", 
            "input-watershed-distance",
            "input-min-open", 
            "input-min-close", 
            "input-min-object", 
            "input-min-hole",
        },
        "controls": _thin_feature_controls,
    },
}
_INITIAL_METHOD = 'Classical'

def segmentation_controls():
    return html.Div(
        children=[
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="md",
                style={"overflow": "hidden"},
                children=[
                    dmc.Text("Segmentation Method", size="md", fw=500, ta="center"),
                    dmc.Space(h=10),
                    dmc.SegmentedControl(
                        id="segment-segcontrol-method",
                        value=_INITIAL_METHOD,
                        color="indigo",
                        data=[{"label": k, "value": k} for k in _SEGMENTATION_METHODS.keys()],
                        fullWidth=True,
                    ),
                    dmc.Space(h=10),
                    *[
                        html.Div(
                            id=method_dict["method_id"],
                            style={"display": "block" if key == _INITIAL_METHOD else "none"},
                            children=method_dict["controls"]()
                        )
                        for key, method_dict in _SEGMENTATION_METHODS.items()
                    ],
                    # dmc.Space(h=10),
                    # dmc.Button(id="button-apply-segmentation", children="Apply Segmentation", fullWidth=True, color="indigo", size="md",)
                ],
            )
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
                                dmc.Image(
                                    id = "image-survey-segmentation",
                                    src = "https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/images/bg-4.png",
                                    h = 800,   
                                    fit="contain",
                                )
                            ], span=5),
                            dmc.GridCol([
                                segmentation_controls(),
                            ], 
                            span=7,
                            style={
                                "padding-left":20,
                                "padding-top":20,
                                "padding-right":20
                            }),

                        ]),
                    ]
                )
            ],
            withBorder=True,
            shadow="sm",
            radius="md",
        )
    ])


