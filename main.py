import plotly.graph_objects as go
import pandas as pd
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 톤의 커스텀 스타일
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
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E8DED3;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 2px 8px rgba(90, 64, 53, 0.06);
    }
    .metric-warning {
        color: #B42318;
        font-weight: 700;
        margin-top: 8px;
        font-size: 0.95rem;
    }
    .insight-box {
        background: #F4F1DE;
        border-left: 5px solid #81B29A;
        padding: 14px 18px;
        border-radius: 8px;
        color: #3D405B;
        margin-top: 8px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    # GitHub Raw URL에서 ZIP 파일을 읽음
    url = (
        "https://raw.githubusercontent.com/tdud-0307/population/main/"
        "population_ts_yearly_gender.zip"
    )
    df = pd.read_csv(url, compression="zip")

    # 가장 최신 연도 데이터만 사용
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    return df_latest, latest_year


# 데이터 로딩
try:
    df, latest_year = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()


# 제목
st.title("🏘️ 우리 동네 인구 피라미드")
st.write(
    f"**{latest_year}년** 기준 전국 읍·면·동의 남녀 연령별 인구 구조를 확인해보세요."
)
st.markdown("---")


# 지역 선택: 시도 -> 시군구 -> 읍·면·동
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도"].dropna().unique())
    selected_sido = st.selectbox("1. 시·도 선택", sido_list)

df_sido = df[df["시도"] == selected_sido]

with col2:

# 화면에 그래프 출력
st.plotly_chart(fig, use_container_width=True)
