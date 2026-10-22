import dash
import dash_bootstrap_components as dbc


# Config to match/Update Port to match FastAPI (8001)
BACKEND_URL = "http://127.0.0.1:8001" #localhost will be flagged by windows defender firewall

# config to assign where the shared local directory will be
from pathlib import Path
BASE_LOCAL_PATH = "../../app_session_data"
Path(BASE_LOCAL_PATH).mkdir(parents=True, exist_ok=True)

# long callback manager in case it is required
from dash import DiskcacheManager
import diskcache
cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    background_callback_manager=background_callback_manager
)

# matplotlib plotting parameters
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('agg')
plt.rcParams['font.size'] = 12 
plt.rcParams['figure.dpi'] = 300