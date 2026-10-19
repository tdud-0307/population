import re
from io import BytesIO

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption("2026년 6월 인구 자료 기준 · 시군구별 65세 이상 인구 비율")


POPULATION_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "sigungu_kr.geojson.txt"
)


@st.cache_data(show_spinner="인구 자료를 불러오는 중...")
def load_population():
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    df = pd.read_csv(
        BytesIO(response.content),
        compression="zip",
        dtype={"코드": "string"},
    )

    required_columns = {"연도", "코드"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "인구 자료에 필요한 열이 없습니다: "
            + ", ".join(sorted(missing_columns))
        )

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["코드"] = df["코드"].astype("string").str.strip()

    df = df[df["연도"] == 2026].copy()

    if df.empty:
        raise ValueError("인구 자료에서 2026년 데이터를 찾지 못했습니다.")

    return df


@st.cache_data(show_spinner="시군구 경계 자료를 불러오는 중...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    if not isinstance(geojson, dict) or "features" not in geojson:
        raise ValueError("시군구 경계 파일이 올바른 GeoJSON 형식이 아닙니다.")

    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        code = properties.get("코드")

        if code is not None:
            properties["코드"] = str(code).strip().split(".")[0].zfill(5)

    return geojson


try:
    population = load_population()
    geojson = load_geojson()

except Exception as error:
    st.error(f"데이터를 불러오지 못했습니다: {error}")
    st.info(
        "GitHub 저장소가 공개되어 있는지, "
        "두 데이터 파일의 주소가 올바른지 확인해 주세요."
    )
    st.stop()


# 연령별 전체 인구 열만 사용합니다.
# 남녀 인구 열을 함께 더하면 중복 집계되므로 사용하지 않습니다.
total_columns = [
    column
    for column in population.columns
    if column.startswith("계_")
]

if not total_columns:
    st.error("'계_0세'와 같은 연령별 인구 열을 찾지 못했습니다.")
    st.stop()


def get_age(column):
    match = re.match(r"^계_(\d+)", column)

    if match:
        return int(match.group(1))

    return None


elderly_columns = [
    column
    for column in total_columns
    if get_age(column) is not None and get_age(column) >= 65
]

if not elderly_columns:
    st.error("65세 이상 인구 열을 찾지 못했습니다.")
    st.stop()


# 인구 열을 숫자로 변환합니다.
for column in total_columns:
    population[column] = pd.to_numeric(
        population[column],
        errors="coerce",
    ).fillna(0)


# 읍·면·동 코드의 앞 5자리를 시군구 코드로 사용합니다.
population["시군구코드"] = (
    population["코드"]
    .astype("string")
    .str.strip()
    .str[:5]
    .str.zfill(5)
)

population["전체인구"] = population[total_columns].sum(axis=1)
population["65세이상인구"] = population[elderly_columns].sum(axis=1)


# 시군구 단위로 인구를 합산합니다.
summary = (
    population.groupby("시군구코드", as_index=False)
    .agg(
        전체인구=("전체인구", "sum"),
        **{"65세이상인구": ("65세이상인구", "sum")},
    )
)

summary["고령화율"] = (
    summary["65세이상인구"]
    .div(summary["전체인구"].where(summary["전체인구"] > 0))
    .mul(100)
)


# GeoJSON에서 시군구 코드와 이름을 가져옵니다.
geo_properties = {}

for feature in geojson["features"]:
    properties = feature.get("properties", {})
    code = properties.get("코드")

    if code is None:
        continue

    code
