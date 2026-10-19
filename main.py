    response = requests.get(url, timeout=60)
    response.raise_for_status()

    from io import BytesIO

    df = pd.read_csv(
        BytesIO(response.content),
        compression="zip",
        dtype={"코드": "string"},
    )

    required = {"연도", "코드"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"인구 데이터에 필요한 열이 없습니다: {', '.join(sorted(missing))}")

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["코드"] = df["코드"].astype("string").str.strip()
    df = df[df["연도"] == 2026].copy()

    if df.empty:
        raise ValueError("인구 데이터에서 2026년 행을 찾지 못했습니다.")

    return df


@st.cache_data(show_spinner="시군구 경계 GeoJSON을 불러오는 중...")
def load_geojson(url: str) -> dict:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    geojson = response.json()

    if not isinstance(geojson, dict) or "features" not in geojson:
        raise ValueError("받아온 파일이 올바른 GeoJSON 형식이 아닙니다.")

    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        raw_code = properties.get("코드")
        if raw_code is not None:
            # 코드가 숫자로 저장된 경우에도 5자리 문자열로 정규화합니다.
            properties["코드"] = str(raw_code).strip().split(".")[0].zfill(5)

    return geojson


try:
    population = load_population(POPULATION_URL)
    geojson = load_geojson(GEOJSON_URL)
except Exception as exc:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {exc}")
    st.info("GitHub 파일 주소, 파일 형식, 저장소 공개 설정을 확인해 주세요.")
    st.stop()


# 연령별 총계 열만 집계합니다. 남_ 및 여_ 열은 합산하지 않습니다.
total_columns = [
    col for col in population.columns
    if col.startswith("계_")
]

if not total_columns:
    st.error("'계_0세' 형식의 연령별 총계 열을 찾지 못했습니다.")
    st.stop()


def age_from_column(column: str):
    """'계_65세' 또는 '계_100세 이상'에서 연령 숫자를 가져옵니다."""
    match = re.match(r"^계_(\d+)", column)
    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        raw_code = properties.get("코드")
        if raw_code is not None:
            # 코드가 숫자로 저장된 경우에도 5자리 문자열로 정규화합니다.
            properties["코드"] = str(raw_code).strip().split(".")[0].zfill(5)

    return geojson


try:
    population = load_population(POPULATION_URL)
    geojson = load_geojson(GEOJSON_URL)
except Exception as exc:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {exc}")
    st.info("GitHub 파일 주소, 파일 형식, 저장소 공개 설정을 확인해 주세요.")
    st.stop()


# 연령별 총계 열만 집계합니다. 남_ 및 여_ 열은 합산하지 않습니다.
total_columns = [
    col for col in population.columns
    if col.startswith("계_")
]

if not total_columns:
    st.error("'계_0세' 형식의 연령별 총계 열을 찾지 못했습니다.")
    st.stop()


def age_from_column(column: str):
    """'계_65세' 또는 '계_100세 이상'에서 연령 숫자를 가져옵니다."""
    match = re.match(r"^계_(\d+)", column)
    return int(match.group(1)) if match else None


elderly_columns = [
    col for col in total_columns
    if (age_from_column(col) is not None and age_from_column(col) >= 65)
]

if not elderly_columns:
    st.error("65세 이상 인구 열을 찾지 못했습니다.")
    st.stop()

# CSV 숫자 열을 수치형으로 바꾸고 결측치는 0으로 처리합니다.
for col in total_columns:
    population[col] = pd.to_numeric(population[col], errors="coerce").fillna(0)

# 읍·면·동 코드 앞 5자리를 시군구 코드로 사용합니다.
population["시군구코드"] = (
    population["코드"].astype("string").str.strip().str[:5].str.zfill(5)
)
population["전체인구"] = population[total_columns].sum(axis=1)
population["65세이상인구"] = population[elderly_columns].sum(axis=1)

summary = (
    population.groupby("시군구코드", dropna=True, as_index=False)
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

# GeoJSON 속성에서 코드와 시군구 이름을 가져옵니다.
geo_properties_by_code = {}
for feature in geojson["features"]:
    props = feature.get("properties", {})
    raw_code = props.get("코드")
    if raw_code is None:
        continue
    code = str(raw_code).strip().split(".")[0].zfill(5)
    props["코드"] = code
    geo_properties_by_code[code] = props

summary["시군구코드"] = summary["시군구코드"].astype("string").str.zfill(5)
summary["시군구"] = summary["시군구코드"].map(
    lambda code: geo_properties_by_code.get(str(code), {}).get("시군구")
)

# 이름이 아닌 코드로 GeoJSON 피처와 인구 집계값을 연결합니다.
summary_by_code = summary.set_index("시군구코드").to_dict("index")
matched_features = []

for feature in geojson["features"]:
    props = feature.get("properties", {})
    code = str(props.get("코드", "")).strip().zfill(5)
    row = summary_by_code.get(code)
    if row is None:
        continue

    rate = row["고령화율"]
    props["고령화율"] = None if pd.isna(rate) else float(rate)
    props["전체인구"] = int(row["전체인구"])
    props["65세이상인구"] = int(row["65세이상인구"])
    matched_features.append(feature)

if not matched_features:
    st.error(
        "인구 데이터와 경계 GeoJSON 사이에 일치하는 시군구 코드가 없습니다. "
        "두 파일의 코드 체계를 확인해 주세요."
    )
    st.stop()

map_geojson = {
    "type": "FeatureCollection",
    "features": matched_features,
}
matched_codes = {
    str(feature["properties"]["코드"]).zfill(5)
    for feature in matched_features
}
map_df = summary[
    summary["시군구코드"].astype(str).str.zfill(5).isin(matched_codes)
].copy()
map_df["코드"] = map_df["시군구코드"].astype(str).str.zfill(5)
map_df["시군구"] = map_df["코드"].map(
    lambda code: geo_properties_by_code.get(code, {}).get("시군구", "이름 없음")
)

valid_rates = map_df["고령화율"].dropna()
metric1, metric2, metric3 = st.columns(3)
with metric1:
    st.metric("지도에 표시된 시군구", f"{len(map_df):,}개")
with metric2:
    st.metric(
        "시군구 고령화율 평균",
        f"{valid_rates.mean():.1f}%" if not valid_rates.empty else "자료 없음",
    )
with metric3:
    st.metric(
        "고령화율 20% 초과",
        f"{int((valid_rates > 20).sum()):,}개" if not valid_rates.empty else "자료 없음",
    )

st.caption(
    f"2026년 인구 데이터 {len(population):,}개 행을 사용했으며, "
    f"코드가 일치하는 시군구 {len(map_df):,}개를 지도에 표시합니다."
)

# 배경 타일 없이 GeoJSON 경계만 그리는 Plotly 단계구분도입니다.
fig = px.choropleth(
    map_df,
    geojson=map_geojson,
    locations="코드",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale="YlOrRd",
    custom_data=["시군구"],
    labels={"고령화율": "고령화율 (%)"},
)
fig.update_traces(
    marker_line_color="#FFFFFF",
    marker_line_width=0.45,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "고령화율: %{z:.2f}%"
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
    height=820,
    margin={"r": 10, "t": 25, "l": 10, "b": 10},
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    coloraxis_colorbar={
        "title": "고령화율 (%)",
        "ticksuffix": "%",
    },
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("### 시군구별 고령화율")
table = map_df[
    ["코드", "시군구", "전체인구", "65세이상인구", "고령화율"]
].copy()
table = table.rename(
    columns={
        "코드": "시군구 코드",
        "전체인구": "전체 인구",
        "65세이상인구": "65세 이상 인구",
        "고령화율": "고령화율 (%)",
    }
)
table["고령화율 (%)"] = table["고령화율 (%)"].round(2)
table = table.sort_values("고령화율 (%)", ascending=False, na_position="last")
st.dataframe(table, use_container_width=True, hide_index=True)
