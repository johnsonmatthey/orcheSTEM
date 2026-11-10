import json
CONFIG_PATH = 'microscope/config.json'

def load_microscope_config(rel_path=CONFIG_PATH):
    """
    Load microscope configuration from JSON file
    """
    try:
        with open(rel_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load microscope configuration: {e}")
        return None

# placed here to be with the global CONFIG_PATH
def save_startup_default(instrument_id, holder):
    """
    Set the instrument and holder in config.json that are connected to on the next startup"""
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    config["instrument"], config["holder"] = instrument_id, holder
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
