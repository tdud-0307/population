import re
from io import BytesIO

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# --------------------------------------------------
# 페이지 설정
# --------------------------------------------------

st.set_page_config(
    page_title="전국 인구 비율 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 인구 비율 단계구분도")
st.caption("연도와 지표를 선택해 시군구별 인구 비율을 비교할 수 있습니다.")


POPULATION_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "sigungu_kr.geojson.txt"
)


# --------------------------------------------------
# 행정구역 코드 통일
# --------------------------------------------------

def normalize_code(value):
    """옛 행정구역 코드를 현재 경계 파일의 코드에 맞춥니다."""
    if value is None or pd.isna(value):
        return None

    code = str(value).strip().split(".")[0]

    if not code:
        return None

    # 시군구 코드가 5자리보다 짧게 읽힌 경우를 보정합니다.
    if len(code) <= 5:
        code = code.zfill(5)

    # 군위군: 47720 -> 27720
    if code.startswith("47720"):
        code = "27720" + code[5:]

    # 강원도 옛 코드: 42 -> 51
    elif code.startswith("42"):
        code = "51" + code[2:]

    # 전라북도 옛 코드: 45 -> 52
    elif code.startswith("45"):
        code = "52" + code[2:]

    return code


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    df = pd.read_csv(
        BytesIO(response.content),
        compression="zip",
        dtype={"코드": "string"},
    )

    required = {"연도", "코드"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "인구 데이터에 필요한 열이 없습니다
