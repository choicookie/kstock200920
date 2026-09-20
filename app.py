import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
from collections import Counter
import time

# 페이지 기본 설정
st.set_page_config(page_title="한국 주간 수익률 분석기 (추세 필터링)", layout="wide")

# CSS를 활용한 이미지 스타일링 (모서리 둥글게, 그림자 효과)
st.markdown("""
<style>
    img {
        border-radius: 12px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 타이틀 및 마스코트 이미지 (상단 화면 분할)
# ---------------------------------------------------------
col_title, col_img = st.columns([8.5, 1.5])

with col_title:
    st.title("📊 한국 주간 수익률 Top 20 다빈도 종목 스크리너")
    st.markdown("최근 3개월간 주간 수익률 상위 20위에 진입한 종목과 최신 주간 Top 30 종목을 요약합니다. **(조건: 20일 이동평균선 상승 추세)**")

with col_img:
    # 깃허브에 업로드할 쿠키 사진 파일명을 정확히 매핑합니다.
    try:
        st.image("시바견_쿠키_2.png", caption="마스코트: 쿠키 🐾", use_container_width=True)
    except:
        st.info("이미지 로딩 대기 중...")

# 유니버스 선택 (통합 옵션 최상단)
universe = st.selectbox(
    "데이터 기준 유니버스를 선택하세요:",
    ("KOSPI + KOSDAQ 전체", "KOSPI 전체", "KOSDAQ 전체", "KOSPI 200", "KOSDAQ 150")
)

# ---------------------------------------------------------
# FinanceDataReader를 활용한 종목 추출
# ---------------------------------------------------------
@st.cache_data
def get_korean_tickers_and_names(universe_choice):
    df_market = pd.DataFrame()
    
    if universe_choice == "KOSPI + KOSDAQ 전체":
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        df_market = pd.concat([df_kospi, df_kosdaq]).drop_duplicates(subset=['Code'])
    elif universe_choice == "KOSPI 전체":
        df_market = fdr.StockListing('KOSPI')
    elif universe_choice == "KOSDAQ 전체":
        df_market = fdr.StockListing('KOSDAQ')
    elif universe_choice == "KOSPI 200":
        df_market = fdr.StockListing('KOSPI')
        df_market = df_market.sort_values(by='Marcap', ascending=False).head(200)
    elif universe_choice == "KOSDAQ 150":
        df_market = fdr.StockListing('KOSDAQ')
        df_market = df_market.sort_values(by='Marcap', ascending=False).head(150)
        
        essential_kosdaq = ['028300', '399720', '160190'] # 관심 종목
        extra_df = fdr.StockListing('KOSDAQ')
        extra_df = extra_df[extra_df['Code'].isin(essential_kosdaq)]
        df_market = pd.concat([df_market, extra_df]).drop_duplicates(subset=['Code'])
        
    ticker_list = df_market['Code'].tolist()
    name_dict = dict(zip(df_market['Code'], df_market['Name']))
    
    return ticker_list, name_dict

# ---------------------------------------------------------
# 실행 메인 로직
# ---------------------------------------------------------
if st.button("데이터 스크리닝 시작", type="primary"):
    
    with st.spinner(f"[{universe}] 종목 리스트를 준비하는 중..."):
        try:
             tickers, name_dict = get_korean_tickers_and_names(universe)
             if not tickers:
                 st.warning("선택하신 시장의 종목 데이터를 찾지 못했습니다.")
                 st.stop()
        except Exception as e:
             st.error(f"종목 데이터를 불러오는 중 오류가 발생했습니다. 상세 에러: {e}")
             st.stop()
    
    # 20일 이동평균선을 계산하려면 3개월치보다 더 이전의 과거 데이터(최소 +20일)가 필요합니다.
    # 안전하게 120일 전부터 데이터를 불러옵니다.
    end_date = datetime.date.today()
    start_date_for_analysis = end_date - datetime.timedelta(days=90) # 주간 수익률 분석 시작일
    start_date_for_download = end_date - datetime.timedelta(days=120) # 데이터 다운로드 시작일 (이평선 계산용)
    
    with st.spinner(f"주가 데이터 수집 및 20일선 추세 필터링 중... 대상 종목이 많아 2~4분 정도 소요될 수 있습니다."):
        
        all_data = []
        progress_bar = st.progress(0)
        total_tickers = len(tickers)
        
        # 1. 일별 주가 데이터 다운로드 및 20일선 필터링
        for i, ticker in enumerate(tickers):
            try:
                # 120일치 일별 데이터 가져오기
                df = fdr.DataReader(ticker, start_date_for_download, end_date)
                
                if not df.empty and len(df) >= 20: # 20일치 이상 데이터가 있는 종목만
                    # 20일 이동평균선(MA20) 계산
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    
                    # [핵심] 최신 2거래일의 20일선 값을 비교하여 추세 확인 (오늘 MA20 > 어제 MA20)
                    latest_ma20 = df['MA20'].iloc[-1]
                    prev_ma20 = df['MA20'].iloc[-2]
                    
                    # 20일선 값이 유효(NaN이 아님)하고, 전일 대비 상승 방향인 종목만 살려둠
                    if pd.notna(latest_ma20) and pd.notna(prev_ma20) and (latest_ma20 > prev_ma20):
                        df['Ticker'] = ticker
                        # 주간 수익률 분석 기간에 해당하는 90일치 데이터만 잘라서 저장 (메모리 최적화)
                        valid_df = df[df.index >= pd.Timestamp(start_date_for_analysis)].copy()
                        if not valid_df.empty:
                            all_data.append(valid_df)
            except Exception:
                pass
            
            # 진행률 업데이트
            if i % 20 == 0 or i == total_tickers - 1:
                progress_bar.progress((i + 1) / total_tickers)
                
        progress_bar.empty()
        
        if not all_data:
            st.error("조건(20일선 상승 추세)을 만족하는 데이터가 없거나 수집에 실패했습니다.")
            st.stop()
            
        # 2. 필터링된 종목들로 데이터 병합
        combined_df = pd.concat(all_data)
        combined_df = combined_df.reset_index()
        
        st.info(f"선택하신 유니버스 중 **'20일선이 상승 방향'**인 종목 {len(all_data)}개가 필터링되어 분석에 사용됩니다.")
        
        # 3. 주간 수익률 분석 진행
        pivot_close = combined_df.pivot(index='Date', columns='Ticker', values='Close')
        weekly_close = pivot_close.resample('W-FRI').last()
        weekly_returns = weekly_close.pct_change().dropna(how='all')
        
        # [최신 주간 Top 30]
        latest_date = weekly_returns.index[-1]
        latest_returns = weekly_returns.loc[latest_date].dropna()
        top30_latest = latest_returns.sort_values(ascending=False).head(30)
        
        top30_data = []
        rank = 1
        for ticker, ret in top30_latest.items():
            kor_name = name_dict.get(ticker, ticker)
            top30_data.append({
                "순위": rank,
                "종목명": kor_name,
                "주간 수익률(%)": round(ret * 100, 2)
            })
            rank += 1
        
        top30_df = pd.DataFrame(top30_data).set_index("순위")
        
        # [3개월 다빈도 랭킹]
        top20_tickers = []
        for date, returns_series in weekly_returns.iterrows():
            top20_weekly = returns_series.sort_values(ascending=False).head(20)
            top20_tickers.extend(top20_weekly.index.tolist())
            
        ticker_counts = Counter(top20_tickers)
        
        result_data = []
        for ticker, count in ticker_counts.items():
            if count >= 2: 
                kor_name = name_dict.get(ticker, ticker)
                result_data.append({"종목명": kor_name, "등장 횟수": count})
                
        result_df = pd.DataFrame(result_data).sort_values(by='등장 횟수', ascending=False)
        result_df = result_df.reset_index(drop=True)
        
    st.success("스크리닝이 완료되었습니다!")
    
    # 결과 화면 출력
    st.header(f"🔥 [20일선 우상향] 최근 주간 ({latest_date.strftime('%Y-%m-%d')} 기준) 수익률 Top 30")
    st.dataframe(top30_df.style.format({"주간 수익률(%)": "{:.2f}%"}), use_container_width=True)
    
    st.divider() 
    
    st.header("🏆 [20일선 우상향] 최근 3개월 주간 수익률 Top 20 다빈도 종목")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("다빈도 랭킹 표")
        st.dataframe(result_df, use_container_width=True)
        
    with col2:
        st.subheader("📌 텍스트 요약 (복사용)")
        max_count = result_df['등장 횟수'].max() if not result_df.empty else 0
        for i in range(max_count, 1, -1):
            freq_stocks = result_df[result_df['등장 횟수'] == i]['종목명'].tolist()
            if freq_stocks:
                st.markdown(f"**■ {i}회 등장 ({len(freq_stocks)}개 종목)**")
                st.code(", ".join(freq_stocks), language="text")