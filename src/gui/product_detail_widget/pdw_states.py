# src/gui/product_detail_widget/pdw_states.py
from enum import Enum

class NewGsProductState(Enum):
    """A Galéria Savaria új termék feltöltési folyamatának állapotait definiálja."""
    IDLE = 0
    FILLING_IN_PROGRESS = 1
    FORM_FILLED = 2
    VALIDATING_IN_PROGRESS = 3