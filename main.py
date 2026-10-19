
target_rows = df_sigungu[df_sigungu["동"] == selected_dong]

if target_rows.empty:
    st.warning("선택한 지역의 데이터가 존재하지 않습니다.")
    st.stop()

target_row = target_rows.iloc[0]


# 0세부터 100세 이상까지 남녀 인구 추출
age_categories = [f"{i}세" for i in range(100)] + ["100세 이상"]
male_pop = []
female_pop = []

for age in age_categories:
    male_col = f"남_{age}"
    female_col = f"여_{age}"

    m_val = target_row[male_col] if male_col in target_row.index else 0
    f_val = target_row[female_col] if female_col in target_row.index else 0

    male_pop.append(0 if pd.isna(m_val) else int(m_val))
    female_pop.append(0 if pd.isna(f_val) else int(f_val))


# 인구 지표 계산
total_population = sum(male_pop) + sum(female_pop)
age_population = [
    male + female for male, female in zip(male_pop, female_pop)
]

# 연령별 인구를 이용한 가중 평균연령 추정
# 100세 이상은 계산 시 100세로 간주
weighted_age_sum = sum(
    age * population
    for age, population in enumerate(age_population[:100])
)
weighted_age_sum += 100 * age_population[100]

average_age = (
    weighted_age_sum / total_population if total_population > 0 else 0
)

# 65세 이상 인구 및 고령화율
elderly_population = sum(age_population[65:])
elderly_rate = (
    elderly_population / total_population * 100
    if total_population > 0
    else 0
)


# 지표 카드 3개 — 반드시 columns 생성 후 각 metric 사용
st.markdown("### 📊 핵심 인구 지표")
metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric("총인구", f"{total_population:,}명")

with metric2:
    st.metric("평균연령", f"{average_age:.1f}세")

with metric3:
st.metric("고령화율", f"{elderly_rate:.1f}%")
    if elderly_rate > 20:
        st.warning("⚠️ 고령화율 20% 초과")

st.caption(
    "평균연령은 연령대별 인구를 이용한 추정치이며, "
    "100세 이상 인구는 계산 시 100세로 간주했습니다."
)
st.markdown("---")


# 인구 피라미드 그래프
male_pop_neg = [-value for value in male_pop]

fig = go.Figure()

fig.add_trace(
    go.Bar(
        y=age_categories,
        x=male_pop_neg,
        name="남성",
        orientation="h",
        marker=dict(color="#E07A5F"),
        hovertemplate="나이: %{y}<br>남성 인구: %{customdata:,}명<extra></extra>",
        customdata=male_pop,
    )
)

fig.add_trace(
    go.Bar(
        y=age_categories,
        x=female_pop,
        name="여성",
        orientation="h",
        marker=dict(color="#81B29A"),
        hovertemplate="나이: %{y}<br>여성 인구: %{x:,}명<extra></extra>",
    )
)

max_val = max(max(male_pop, default=0), max(female_pop, default=0))
max_val = max(max_val, 1)
tick_step = max(1, max_val // 4)
tick_vals = list(range(-max_val, max_val + tick_step, tick_step))
tick_text = [f"{abs(value):,}" for value in tick_vals]

fig.update_layout(
    title=dict(
        text=f"<b>{selected_sido} {selected_sigungu} {selected_dong}</b> 인구 피라미드",
        font=dict(size=20, color="#3D405B"),
    ),
    barmode="overlay",
    bargap=0.1,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#F4F1DE",
    xaxis=dict(
        title="인구수 (명)",
        tickmode="array",
        tickvals=tick_vals,
        ticktext=tick_text,
        gridcolor="#E0DDCF",
        zeroline=True,
        zerolinecolor="#A8A29E",
    ),
    yaxis=dict(
        title="연령",
        type="category",
        categoryorder="array",
        categoryarray=age_categories,
        gridcolor="#E0DDCF",
    ),
    legend=dict(x=0.85, y=1.05, orientation="h"),
    height=850,
    margin=dict(l=40, r=30, t=80, b=40),
)

st.plotly_chart(fig, use_container_width=True)


# 아이(0~14세)와 어르신(65세 이상) 인구 비교 문장
children_population = sum(age_population[:15])

if children_population > elderly_population:
    insight = (
        f"이 동네는 0~14세 인구가 {children_population:,}명으로 "
        f"65세 이상 어르신 {elderly_population:,}명보다 많아, "
        "상대적으로 아이가 많은 편입니다."
    )
elif children_population < elderly_population:
    insight = (
        f"이 동네는 65세 이상 어르신이 {elderly_population:,}명으로 "
        f"0~14세 아이 {children_population:,}명보다 많아, "
        "상대적으로 어르신이 많은 편입니다."
    )
else:
    insight = (
        f"이 동네는 0~14세 인구와 65세 이상 인구가 모두 "
        f"{children_population:,}명으로 같습니다."
    )

st.markdown(
    f'<div class="insight-box">💡 <b>이 동네는 아이가 많은 편인가요, '
    f'어르신이 많은 편인가요?</b><br>{insight}</div>',
    unsafe_allow_html=True,
)
