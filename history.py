import uuid
from datetime import datetime

import streamlit as st

KEY = "history_records"


def load_records():
    """Sirf is browser session ki reports. Doosre users ko nazar nahi aati."""
    return list(st.session_state.get(KEY, []))


def save_record(file_name, file_hash, parsed, result):
    records = st.session_state.setdefault(KEY, [])
    for r in records:
        if r.get("file_hash") == file_hash:
            return r
    rec = {
        "id": uuid.uuid4().hex[:8],
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_name": file_name,
        "file_hash": file_hash,
        "values": parsed["values"],
        "ratios": parsed["ratios"],
        "warnings": parsed["warnings"],
        "result": result,
    }
    records.append(rec)
    return rec