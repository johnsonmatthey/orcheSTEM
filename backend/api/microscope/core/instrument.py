import json
from dataclasses import dataclass, field
from pathlib import Path

INSTRUMENTS_DIR = Path(__file__).resolve().parent.parent / "instruments"


@dataclass
class Instrument:
    """
    The specific instrument loaded in, info grouped up based on the instruments/instrument_id.json
    """
    instrument_id: str       # the JSON file name without .json; unique per physical instrument
    config_path: Path        # the JSON file path of the instrument config
    vendor: str              # e.g. jeol, thermo etc.
    display_name: str        # display label for the UI
    microscope_model: str    # the vendor's model name, e.g. GrandARM; descriptive only
    connections: dict        # {"pyjem": {"hostname": ...}, "merlin": {"hostname": ...}}
    hardware: dict           # {category: {method: settings}} -  a method not listed is unavailable
    holders: list            # sample holders that selected on this instrument as some calibrations depend on the holder and may have linked capabilityies e.g heating
    preferences: dict = field(default_factory=dict) # factory to give each instance a new dict rather than 1 mutable dict

    def has(self, category: str, method: str) -> bool:
        """Does the instrument declare this method under this category, e.g. has("imaging", "qd_scanengine")?"""
        return method in self.hardware.get(category, {})

    def options(self, category: str, method: str) -> dict:
        """Settings the JSON gives a hardware method (the `name` of a Method class, e.g. "qd_scanengine") under a category,
        such as {"enabled_inputs": [3]}. Raises ValueError if the instrument doesn't declare that method for the category."""
        if not self.has(category, method):
            declared_methods = sorted(self.hardware.get(category, {})) # method names listed under this category in the json
            raise ValueError(f"Instrument '{self.instrument_id}' has no {category} method '{method}'. Available methods: {declared_methods}")
        return self.hardware[category][method]

    def save_preferences(self, control: dict, stem4d_settings: dict | None = None, stemsi_settings: dict | None = None):
        """store user preferences back into the instrument's config file."""
        self.preferences["control"] = control
        if stem4d_settings is not None:
            self.preferences.setdefault("4dstem", {}).update(stem4d_settings)
        if stemsi_settings is not None:
            self.preferences.setdefault("stemsi", {}).update(stemsi_settings)
        data = json.loads(self.config_path.read_text())
        data["preferences"] = self.preferences
        self.config_path.write_text(json.dumps(data, indent=4))


def list_instruments() -> list[str]:
    return sorted(instrument_filename.stem for instrument_filename in INSTRUMENTS_DIR.glob("*.json"))


def load_instrument(instrument_id: str) -> Instrument:
    config_path = INSTRUMENTS_DIR / f"{instrument_id}.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Unknown instrument '{instrument_id}'. Available: {list_instruments()}")

    data = json.loads(config_path.read_text())
    if not data.get("vendor"):
        raise ValueError(f"{config_path.name}: 'vendor' is required (e.g. jeol)")
    hardware = data.get("hardware", {})

    return Instrument(
        instrument_id=instrument_id,
        config_path=config_path,
        vendor=data["vendor"],
        display_name=data.get("display_name", data.get("microscope_model", instrument_id)),
        microscope_model=data.get("microscope_model", instrument_id),
        connections=data.get("connections", {}),
        hardware=hardware,
        holders=data.get("holders", []),
        preferences=data.get("preferences", {}),
    )
