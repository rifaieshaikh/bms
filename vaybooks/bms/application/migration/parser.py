from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, List, Union

import pandas as pd


def load_upload(file_bytes: bytes, filename: str = "") -> pd.DataFrame:
    """Load CSV or Excel upload into a DataFrame, preserving source headers."""
    name = (filename or "").lower()
    buffer = BytesIO(file_bytes)
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(buffer, dtype=object)
    else:
        df = pd.read_csv(buffer, dtype=object)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() if c is not None else "" for c in df.columns]
    # Drop unnamed empty columns from Excel
    df = df.loc[:, [c for c in df.columns if c and not str(c).lower().startswith("unnamed")]]
    return df.reset_index(drop=True)


def source_columns(df: pd.DataFrame) -> List[str]:
    return [str(c) for c in df.columns]


def load_from_fileobj(fileobj: Union[BinaryIO, BytesIO], filename: str = "") -> pd.DataFrame:
    data = fileobj.read()
    if isinstance(data, str):
        data = data.encode("utf-8")
    return load_upload(data, filename)
