except Exception as exc:
    st.error(f"데이터를 불러오지 못했습니다: {exc}")
    st.info("GitHub 파일 주소와 파일 형식을 확인한 뒤 앱을 다시 실행해 주세요.")
    st.stop()


# 나이별 총계 열만 사용합니다. 남_ / 여_ 열은 합산하지 않습니다.
total_age_columns = [
    column
    for column in population.columns
    if column.startswith("계_")
]

if not total_age_columns:
    st.error("'계_0세' 형식의 나이별 총계 열을 찾지 못했습니다.")
    st.stop()

# 65세부터 100세 이상까지 열을 이름 기준으로 선택합니다.
elderly_columns = []
for column in total_age_columns:
    age_label = column.removeprefix("계_").removesuffix("세")
    if age_label == "100세 이상":
        elderly_columns.append(column)
    else:
        try:
            if int(age_label) >= 65:
                elderly_columns.append(column)
        except ValueError:
            continue

if not elderly_columns:
    st.error("65세 이상 인구 열('계_65세'~'계_100세 이상')을 찾지 못했습니다.")
    st.stop()

# 동 코드 앞 5자리를 시군구 코드로 사용합니다.
population["시군구코드"] = (
    population["코드"].astype("string").str.strip().str[:5]
)

for column in set(total_age_columns + elderly_columns):
    population[column] = pd.to_numeric(population[column], errors="coerce").fillna(0)

population["전체인구"] = population[total_age_columns].sum(axis=1)
population["65세이상인구"] = population[elderly_columns].sum(axis=1)

# 읍·면·동 행을 시군구 코드별로 합산한 뒤 비율을 계산합니다.
summary = (
    population.groupby("시군구코드", dropna=True)
    .agg(
        전체인구=("전체인구", "sum"),
        **{"65세이상인구": ("65세이상인구", "sum")},
    )
    .reset_index()
)
summary["고령화율"] = (
    summary["65세이상인구"]
    .div(summary["전체인구"].where(summary["전체인구"] != 0))
    .mul(100)
)

# GeoJSON 코드와 집계 코드 모두 5자리 문자열로 맞춥니다.
geo_codes = {
    str(feature.get("properties", {}).get("코드", "")).strip().zfill(5)
    for feature in geojson["features"]
}
summary["시군구코드"] = summary["시군구코드"].astype("string").str.zfill(5)

# 이름이 아닌 코드로 GeoJSON feature를 필터링하고, 집계값을 속성에 넣습니다.
summary_lookup = summary.set_index("시군구코드").to_dict("index")
matched_features = []

for feature in geojson["features"]:
    properties = feature.setdefault("properties", {})
    code = str(properties.get("코드", "")).strip().zfill(5)
    if code in summary_lookup:
        row = summary_lookup[code]
        properties["고령화율"] = (
            None if pd.isna(row["고령화율"]) else round(float(row["고령화율"]), 2)
        )
        properties["전체인구"] = int(row["전체인구"])
        properties["65세이상인구"] = int(row["65세이상인구"])
        matched_features.append(feature)

map_geojson = {
    "type": "FeatureCollection",
    "features": matched_features,
}

if not matched_features:
    st.error(
        "인구 데이터와 GeoJSON의 시군구 코드가 하나도 일치하지 않습니다. "
        "두 파일의 코드 체계를 확인해 주세요."
    )
    st.stop()

matched_codes = {
    str(feature["properties"]["코드"]).zfill(5) for feature in matched_features
}
matched_summary = summary[summary["시군구코드"].isin(matched_codes)].copy()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("표시 시군구", f"{len(matched_features):,}개")
with col2:
    valid_rates = matched_summary["고령화율"].dropna()
    st.metric(
        "평균 고령화율",
        f"{valid_rates.mean():.1f}%" if not valid_rates.empty else "자료 없음",
    )
with col3:
    st.metric(
        "고령화율 20% 초과",
        f"{(valid_rates > 20).sum():,}개" if not valid_rates.empty else "자료 없음",
    )

st.caption(
    f"2026년 데이터 행 {len(population):,}개 · "
    f"인구와 경계가 코드로 일치한 시군구 {len(matched_features):,}개"
)

# plotly 단계구분도: 타일 배경 없이 GeoJSON 경계만 표시합니다.
map_df = matched_summary.rename(columns={"시군구코드": "코드"}).copy()
map_df["코드"] = map_df["코드"].astype(str).str.zfill(5)
map_df["고령화율"] = pd.to_numeric(map_df["고령화율"], errors="coerce")

fig = px.choropleth(
    map_df,
    geojson=map_geojson,
    locations="코드",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale="YlOrRd",
    labels={"고령화율": "고령화율 (%)"},
    hover_data={"코드": False, "고령화율": ":.2f"},
    custom_data=["코드"],
)

# GeoJSON 속성의 시군구 이름을 hover에 포함합니다.
name_by_code = {
    str(feature["properties"].get("코드", "")).zfill(5):
        feature["properties"].get("시군구", "이름 없음")
    for feature in matched_features
}
fig.update_traces(
    marker_line_color="#FFFFFF",
    marker_line_width=0.45,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "고령화율: %{z:.2f}%<extra></extra>"
    ),
)

# Hover 제목에 시군구 이름을 표시하기 위해 위치 코드 대신 이름을 customdata로 사용
name_data = map_df["코드"].map(name_by_code).fillna("이름 없음").tolist()
fig.update_traces(
    customdata=[[name] for name in name_data],
    hovertemplate="<b>%{customdata[0]}</b><br>고령화율: %{z:.2f}%<extra></extra>",
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
    height=850,
    margin={"r": 10, "t": 25, "l": 10, "b": 10},
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    coloraxis_colorbar={
        "title": "고령화율 (%)",
        "ticksuffix": "%",
    },
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("### 고령화율 시군구별 데이터")
table = matched_summary.copy()
table = table.rename(
    columns={
        "시군구코드": "시군구 코드",
        "전체인구": "전체 인구",
        "65세이상인구": "65세 이상 인구",
        "고령화율": "고령화율 (%)",
    }
)
table["고령화율 (%)"] = table["고령화율 (%)"].round(2)
)
