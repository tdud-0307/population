with metric2:
    st.metric("평균연령", f"{average_age:.1f}세")

with metric3:
    st.metric("고령화율", f"{elderly_rate:.1f}%")
    if elderly_rate > 20:
        st.markdown(
            '<div class="metric-warning">⚠️ 고령화율 20% 초과</div>',
            unsafe_allow_html=True,
        )

st.caption(
    "평균연령은 연령대별 인구를 이용한 추정치이며, "
    "100세 이상 인구는 계산 시 100세로 간주했습니다."
)
st.markdown("---")


# 인구 피라미드
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


# 아이와 어르신 중 어느 쪽이 많은지 자동 설명
children_population = sum(age_population[:15])  # 0~14세
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
