import plotly.graph_objects as go
import pandas as pd
import streamlit as st

# 페이지 기본 설정 (타이틀 및 레이아웃)
st.set_page_config(
    page_title="동네별 인구 피라미드", page_icon="🏘️", layout="wide"
)

# 따뜻한 톤의 커스텀 스타일 적용 (배경 및 폰트 감성)
st.markdown(
    """
    <style>
    .main {
        background-color: #FAF8F5;
    }
    h1 {
        color: #5A4035;
        font-family: 'Nanum Gothic', sans-serif;
    }
    .stSelectbox label {
        color: #6C5B52 !important;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 데이터 불러오기 (캐싱을 통해 속도 최적화)
@st.cache_data
def load_data():
    # GitHub Blob URL을 Raw 파일 다운로드 URL로 변환
    url = "https://raw.githubusercontent.com/tdud-0307/population/main/population_ts_yearly_gender.zip"

    # pandas는 zip 파일 내부의 csv를 자동으로 압축 해제해서 읽습니다.
    df = pd.read_csv(url, compression="zip")

    # 가장 최신 연도 데이터만 필터링
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    return df_latest, latest_year


# 데이터 로딩
try:
    df, latest_year = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 앱 헤더 영역
st.title("🏘️ 우리 동네 인구 피라미드")
st.write(
    f"**{latest_year}년** 기준 전국 읍·면·동의 남녀 연령별 인구 구조를 확인해보세요."
)
st.markdown("---")

# 1. 지역 선택 드롭다운 (시도 -> 시군구 -> 동)
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도"].dropna().unique())
    selected_sido = st.selectbox("1. 시·도 선택", sido_list)

# 선택한 시도에 해당하는 시군구 필터링
df_sido = df[df["시도"] == selected_sido]

with col2:
    sigungu_list = sorted(df_sido["시군구"].dropna().unique())
    selected_sigungu = st.selectbox("2. 시·군·구 선택", sigungu_list)

# 선택한 시군구에 해당하는 동 필터링
df_sigungu = df_sido[df_sido["시군구"] == selected_sigungu]

with col3:
    dong_list = sorted(df_sigungu["동"].dropna().unique())
    selected_dong = st.selectbox("3. 읍·면·동 선택", dong_list)

# 선택된 최종 행 추출
target_row = df_sigungu[df_sigungu["동"] == selected_dong]

if target_row.empty:
    st.warning("선택한 지역의 데이터가 존재하지 않습니다.")
    st.stop()

# 2. 나이 라벨 및 데이터 추출 준비
# 0세부터 100세 이상까지 순서대로 라벨 리스트 생성
age_categories = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_pop = []
female_pop = []

for age in age_categories:
    male_col = f"남_{age}"
    female_col = f"여_{age}"

    # 해당 컬럼이 존재하면 값을 가져오고, 없으면 0 처리
    m_val = target_row[male_col].values[0] if male_col in target_row else 0
    f_val = target_row[female_col].values[0] if female_col in target_row else 0

    male_pop.append(m_val)
    female_pop.append(f_val)

# 피라미드 그래프 생성을 위해 남성 인구수는 음수로 변환
male_pop_neg = [-val for val in male_pop]

# 3. Plotly 가로 막대 그래프 그리기
fig = go.Figure()

# 남성 데이터 (왼쪽, 음수 값) - 따뜻한 코랄/브릭 톤
fig.add_trace(
    go.Bar(
        y=age_categories,
        x=male_pop_neg,
        name="남성",
        orientation="h",
        marker=dict(color="#E07A5F"),
        hovertemplate="나이: %{y}<br>남성 인구: %{customdata:,}명<extra></extra>",
        customdata=male_pop,  # 마우스 올렸을 때 양수로 표시
    )
)

# 여성 데이터 (오른쪽, 양수 값) - 따뜻한 앰버/세이지 톤
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

# x축 눈금 레이블을 절대값(양수)으로 변환하여 보기 좋게 설정
max_val = max(max(male_pop), max(female_pop)) if male_pop and female_pop else 100
# 적절한 눈금 간격 설정
tick_step = max(1, max_val // 4)
tick_vals = list(range(-max_val, max_val + tick_step, tick_step))
tick_text = [f"{abs(v):,}" for v in tick_vals]

# 그래프 레이아웃 및 축 설정
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
    ),
    # y축: 0세가 맨 아래, 100세 이상이 맨 위로 오도록 age_categories 순서 고정
    yaxis=dict(
        title="연령",
        type="category",
        categoryorder="array",
        categoryarray=age_categories,  # 0세부터 100세 이상 순서 고정
        gridcolor="#E0DDCF",
    ),
    legend=dict(x=0.85, y=1.05, orientation="h"),
    height=850,
)

# 화면에 그래프 출력
st.plotly_chart(fig, use_container_width=True)
