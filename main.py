import re
from io import BytesIO

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# ==================================================
# 1. 페이지 설정
# ==================================================

st.set_page_config(
    page_title="전국 인구 비율 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 인구 비율 단계구분도")
st.caption("연도·시도·인구 지표를 선택하여 행정구역별 인구 비율을 비교합니다.")

POPULATION_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/tdud-0307/population/main/"
    "sigungu_kr.geojson.txt"
)


# ==================================================
# 2. 행정구역 코드 통일
# ==================================================

def normalize_code(value):
    """옛 행정구역 코드를 경계 파일의 코드 체계에 맞춥니다."""
    if value is None or pd.isna(value):
        return None

    code = str(value).strip().split(".")[0]

    if not code or code.lower() in ("nan", "none", "<na>"):
        return None

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


# ==================================================
# 3. 데이터 불러오기
# ==================================================

@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    df = pd.read_csv(
        BytesIO(response.content),
        compression="zip",
        dtype={"코드": "string"},
    )

    df.columns = df.columns.astype(str).str.strip()

    required = {"연도", "코드"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "인구 데이터에 필요한 열이 없습니다: "
            + ", ".join(sorted(missing))
        )

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["코드"] = df["코드"].astype("string").str.strip()

    return df


@st.cache_data(show_spinner="행정구역 경계 데이터를 불러오는 중...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    if not isinstance(geojson, dict) or "features" not in geojson:
        raise ValueError("경계 파일이 올바른 GeoJSON 형식이 아닙니다.")

    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        code = normalize_code(properties.get("코드"))

        if code is not None:
            properties["코드"] = code[:5]

    return geojson


try:
    population_all = load_population()
    geojson_all = load_geojson()

except Exception as error:
    st.error(f"데이터를 불러오지 못했습니다: {error}")
    st.info(
        "GitHub 저장소가 공개되어 있는지, "
        "인구 ZIP 파일과 GeoJSON 주소가 올바른지 확인해 주세요."
    )
    st.stop()


# ==================================================
# 4. 연령별 인구 열 확인
# ==================================================

total_columns = [
    column
    for column in population_all.columns
    if column.startswith("계_")
]


def get_age(column):
    """'계_65세', '계_100세 이상' 등에서 연령을 추출합니다."""
    match = re.match(r"^계_(\d+)", column)
    return int(match.group(1)) if match else None


if not total_columns:
    st.error("'계_0세' 형식의 연령별 총계 열을 찾지 못했습니다.")
    st.stop()


elderly_columns = [
    column
    for column in total_columns
    if get_age(column) is not None and get_age(column) >= 65
]

youth_columns = [
    column
    for column in total_columns
    if get_age(column) is not None and 0 <= get_age(column) <= 14
]

if not elderly_columns:
    st.error("65세 이상 인구 열을 찾지 못했습니다.")
    st.stop()

if not youth_columns:
    st.error("0~14세 인구 열을 찾지 못했습니다.")
    st.stop()


# ==================================================
# 5. 사용자 선택: 연도, 지표, 시도
# ==================================================

available_years = sorted(
    population_all["연도"].dropna().astype(int).unique().tolist()
)

if not available_years:
    st.error("인구 데이터에서 사용 가능한 연도를 찾지 못했습니다.")
    st.stop()


province_names = sorted(
    {
        str(feature.get("properties", {}).get("시도", "")).strip()
        for feature in geojson_all["features"]
        if str(
            feature.get("properties", {}).get("시도", "")
        ).strip()
    }
)

st.subheader("분석 조건")

control1, control2, control3 = st.columns(3)

with control1:
    selected_year = st.select_slider(
        "연도 선택",
        options=available_years,
        value=max(available_years),
        format_func=lambda year: f"{year}년",
    )

with control2:
    selected_indicator = st.selectbox(
        "분석 지표",
        [
            "고령화율 (65세 이상)",
            "유소년 비율 (0~14세)",
        ],
    )

with control3:
    selected_province = st.selectbox(
        "확대할 시도",
        ["전국"] + province_names,
    )


# ==================================================
# 6. 지표별 색 구간 설정
# ==================================================

if selected_indicator == "고령화율 (65세 이상)":
    target_columns = elderly_columns
    indicator_name = "고령화율"
    target_population_name = "65세 이상 인구"

    # 연도에 상관없이 항상 동일한 경계값을 사용합니다.
    boundary_values = [19, 23, 28, 38]

    range_labels = [
        "19% 이하",
        "19% 초과~23% 이하",
        "23% 초과~28% 이하",
        "28% 초과~38% 이하",
        "38% 초과",
        "자료 없음",
    ]

else:
    target_columns = youth_columns
    indicator_name = "유소년 비율"
    target_population_name = "0~14세 인구"

    # 유소년 비율은 고령화율과 다른 구간을 사용합니다.
    boundary_values = [5, 8, 11, 14]

    range_labels = [
        "5% 이하",
        "5% 초과~8% 이하",
        "8% 초과~11% 이하",
        "11% 초과~14% 이하",
        "14% 초과",
        "자료 없음",
    ]


# 낮은 비율은 밝은색, 높은 비율은 진한색으로 표시합니다.
color_map = {
    range_labels[0]: "#FFF7BC",
    range_labels[1]: "#FEC44F",
    range_labels[2]: "#FE9929",
    range_labels[3]: "#EC7014",
    range_labels[4]: "#B30000",
    "자료 없음": "#BDBDBD",
}


def classify_rate(rate):
    """비율을 해당 지표의 고정된 색 구간에 배정합니다."""
    if rate is None or pd.isna(rate):
        return "자료 없음"

    if rate <= boundary_values[0]:
        return range_labels[0]

    if rate <= boundary_values[1]:
        return range_labels[1]

    if rate <= boundary_values[2]:
        return range_labels[2]

    if rate <= boundary_values[3]:
        return range_labels[3]

    return range_labels[4]


# ==================================================
# 7. 선택한 연도의 인구 계산
# ==================================================

population = population_all[
    population_all["연도"] == selected_year
].copy()

if population.empty:
    st.error(f"{selected_year}년 인구 데이터가 없습니다.")
    st.stop()


# 연령별 총계 열만 숫자로 변환합니다.
for column in total_columns:
    population[column] = pd.to_numeric(
        population[column],
        errors="coerce",
    ).fillna(0)


# 읍·면·동 코드를 현재 코드 체계로 통일합니다.
population["정규화코드"] = population["코드"].map(normalize_code)

population["시군구코드"] = (
    population["정규화코드"]
    .map(lambda code: code[:5] if code else None)
)

population["전체인구"] = population[total_columns].sum(axis=1)
population["대상인구"] = population[target_columns].sum(axis=1)


# 시군구 단위로 전체 인구와 대상 인구를 합산합니다.
summary = (
    population
    .dropna(subset=["시군구코드"])
    .groupby("시군구코드", as_index=False)
    .agg(
        전체인구=("전체인구", "sum"),
        대상인구=("대상인구", "sum"),
    )
)

summary["비율"] = (
    summary["대상인구"]
    .div(summary["전체인구"].where(summary["전체인구"] > 0))
    .mul(100)
)

summary["시군구코드"] = (
    summary["시군구코드"].astype(str).str.zfill(5)
)


# ==================================================
# 8. GeoJSON과 인구 데이터 연결
# ==================================================

summary_by_code = summary.set_index("시군구코드").to_dict("index")

map_features = []
map_rows = []

for feature in geojson_all["features"]:
    properties = feature.get("properties", {})
    code = normalize_code(properties.get("코드"))

    if code is None:
        continue

    # 경계 데이터는 시군구 코드 5자리로 연결합니다.
    code = code[:5]
    properties["코드"] = code

    province = str(properties.get("시도", "")).strip()
    district = str(properties.get("시군구", "")).strip()

    row = summary_by_code.get(code)

    if row is None:
        rate = None
        total_population = None
        target_population = None
    else:
        rate = row["비율"]

        if pd.isna(rate):
            rate = None

        total_population = int(row["전체인구"])
        target_population = int(row["대상인구"])

    # 값이 없는 지역도 경계 목록에 유지해 회색으로 표시합니다.
    properties["비율"] = rate

    map_features.append(feature)

    map_rows.append(
        {
            "코드": code,
            "시도": province,
            "시군구": district,
            "비율": rate,
            "구간": classify_rate(rate),
            "전체인구": total_population,
            "대상인구": target_population,
        }
    )


map_df = pd.DataFrame(map_rows)

if map_df.empty:
    st.error("지도에 표시할 행정구역 경계를 찾지 못했습니다.")
    st.stop()


# ==================================================
# 9. 전국 지표 카드 계산
# ==================================================

# 전국 비율은 선택한 연도의 전체 읍·면·동 인구 합계로 계산합니다.
national_total = population["전체인구"].sum()
national_target = population["대상인구"].sum()

if national_total > 0:
    national_rate = national_target / national_total * 100
else:
    national_rate = None


valid_df = map_df[map_df["비율"].notna()].copy()

if not valid_df.empty:
    highest_row = valid_df.loc[valid_df["비율"].idxmax()]
    lowest_row = valid_df.loc[valid_df["비율"].idxmin()]

    highest_name = f"{highest_row['시도']} {highest_row['시군구']}".strip()
    lowest_name = f"{lowest_row['시도']} {lowest_row['시군구']}".strip()

    highest_value = f"{highest_row['비율']:.2f}%"
    lowest_value = f"{lowest_row['비율']:.2f}%"
else:
    highest_name = "자료 없음"
    lowest_name = "자료 없음"
    highest_value = "자료 없음"
    lowest_value = "자료 없음"


st.subheader(f"{selected_year}년 주요 지표")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        f"전국 {indicator_name}",
        f"{national_rate:.2f}%"
        if national_rate is not None
        else "자료 없음",
    )

with card2:
    st.metric("가장 높은 시군구", highest_value)
    st.caption(highest_name)

with card3:
    st.metric("가장 낮은 시군구", lowest_value)
    st.caption(lowest_name)


# ==================================================
# 10. 전국 또는 선택한 시도 표시
# ==================================================

if selected_province == "전국":
    display_df = map_df.copy()

    display_features = map_features

else:
    display_df = map_df[
        map_df["시도"] == selected_province
    ].copy()

    display_features = [
        feature
        for feature in map_features
        if str(
            feature.get("properties", {}).get("시도", "")
        ).strip() == selected_province
    ]


if display_df.empty or not display_features:
    st.warning(
        f"{selected_province}의 행정구역 경계 또는 인구 자료를 찾지 못했습니다."
    )
    st.stop()


display_geojson = {
    "type": "FeatureCollection",
    "features": display_features,
}


# ==================================================
# 11. 단계구분도 그리기
# ==================================================

st.subheader(
    f"{selected_year}년 {selected_province} {indicator_name} 지도"
)

fig = px.choropleth(
    display_df,
    geojson=display_geojson,
    locations="코드",
    featureidkey="properties.코드",
    color="구간",
    color_discrete_map=color_map,
    category_orders={"구간": range_labels},
    custom_data=[
        "시도",
        "시군구",
        "비율",
        "전체인구",
        "대상인구",
    ],
)

fig.update_traces(
    marker_line_color="white",
    marker_line_width=0.5,
    hovertemplate=(
        "<b>%{customdata[0]} %{customdata[1]}</b><br>"
        f"{indicator_name}: %{{customdata[2]:.2f}}%<br>"
        "전체 인구: %{customdata[3]:,}명<br>"
        f"{target_population_name}: %{{customdata[4]:,}}명"
        "<extra></extra>"
    ),
)

fig.update_geos(
    visible=False,
    showcountries=False,
    showcoastlines=False,
    showland=False,
    showframe=False,
    fitbounds="locations",
    bgcolor="rgba(0,0,0,0)",
)

fig.update_layout(
    height=800,
    margin=dict(
        r=10,
        t=25,
        l=10,
        b=10,
    ),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend_title_text=f"{indicator_name} 구간",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=0.01,
        xanchor="left",
        x=0,
    ),
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ==================================================
# 12. 코드 불일치 안내
# ==================================================

unmatched_count = int(display_df["비율"].isna().sum())

if unmatched_count > 0:
    st.warning(
        f"안내: 현재 지도 범위에서 {unmatched_count}개 시군구는 "
        "인구 자료가 연결되지 않아 회색으로 표시했습니다. "
        "옛 코드 42→51(강원), 45→52(전북), "
        "47720→27720(군위군) 변환을 적용했습니다. "
        "변환 후에도 일치하지 않는 지역은 자료의 코드 체계를 추가로 확인해야 합니다."
    )
else:
    st.info(
        "현재 지도 범위의 모든 시군구에 인구 자료가 연결되었습니다."
    )


# ==================================================
# 13. 시군구별 상세 표
# ==================================================

st.subheader("시군구별 상세 데이터")

table = display_df[
    [
        "코드",
        "시도",
        "시군구",
        "전체인구",
        "대상인구",
        "비율",
        "구간",
    ]
].copy()

table = table.rename(
    columns={
        "코드": "시군구 코드",
        "전체인구": "전체 인구",
        "대상인구": target_population_name,
        "비율": f"{indicator_name} (%)",
        "구간": "색상 구간",
    }
)

table[f"{indicator_name} (%)"] = table[
    f"{indicator_name} (%)"
].round(2)

table = table.sort_values(
    f"{indicator_name} (%)",
    ascending=False,
    na_position="last",
)

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)
