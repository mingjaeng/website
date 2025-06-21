import os
import json
import time
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect

import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

import markdown

# 기업명 - 종목코드 매핑
COMPANY_CODES = {
    "AP위성": "052860",
    "데브시스터즈": "194480",
    "한선엔지니어링": "060560",
    "고려제강": "002240",
    "메카로": "089010",
    "미래에셋증권": "006800",
    "폴라리스AI": "230360",
    "로보로보": "100660",
    "셀바스헬스케어": "208370",
    "성우하이텍": "015750",
}

# 홈 리디렉션 (루트 접속 시 외부 페이지로 이동)
def home_redirect(request):
    return redirect('https://mingjaeng.github.io/capsyon-design/')

# 기업명으로 종목코드 찾기 (네이버 금융 크롤링)
def get_stock_code(company_name):
    search_url = f"https://finance.naver.com/search/searchList.naver?query={company_name}"
    res = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    a_tag = soup.select_one('ul.searchList li a')
    if a_tag:
        href = a_tag.get('href')
        if 'code=' in href:
            return href.split('code=')[-1]
    return None

# 종목코드로 주가 정보 가져오기
def get_stock_info(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    try:
        price = soup.select_one('p.no_today span.blind').text
        change = soup.select_one('p.no_exday span.blind').text
        rate = soup.select('p.no_exday span')[-1].text.strip()
        return price, change, rate
    except:
        return None, None, None

# 경제지표 정보 가져오기
def get_economic_indicators():
    indicators = {}
    market_url = 'https://finance.naver.com/marketindex/'
    res = requests.get(market_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')

    try:
        usd_tag = soup.select_one('div.market1 ul.data_lst li:nth-of-type(1) span.value')
        indicators['USD/KRW'] = usd_tag.text.strip() if usd_tag else None
    except:
        indicators['USD/KRW'] = None

    try:
        gold_items = soup.select("ul.data_lst li")
        for item in gold_items:
            title_tag = item.select_one('h3')
            if title_tag and '국내 금' in title_tag.text:
                gold_value = item.select_one('.value')
                indicators['국내 금'] = gold_value.text.strip() if gold_value else None
                break
        else:
            indicators['국내 금'] = None
    except:
        indicators['국내 금'] = None

    try:
        sise_url = 'https://finance.naver.com/sise/'
        res2 = requests.get(sise_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup2 = BeautifulSoup(res2.text, 'html.parser')
        indicators['KOSPI'] = soup2.select_one('#KOSPI_now').text.strip()
        indicators['KOSDAQ'] = soup2.select_one('#KOSDAQ_now').text.strip()
    except:
        indicators['KOSPI'] = None
        indicators['KOSDAQ'] = None

    return indicators

# API: 주식 정보 + 경제지표 JSON 응답
def stock_info_api(request):
    company_name = request.GET.get('name')
    if not company_name:
        return JsonResponse({'error': '기업명을 입력하세요'}, status=400)

    code = get_stock_code(company_name)
    if not code:
        return JsonResponse({'error': '종목코드를 찾을 수 없습니다'}, status=404)

    price, change, rate = get_stock_info(code)
    econ = get_economic_indicators()

    result = {
        '기업명': company_name,
        '종목코드': code,
        '현재가': price,
        '전일비': change,
        '등락률': rate,
        'USD/KRW': econ['USD/KRW'],
        '국내 금': econ['국내 금'],
        'KOSPI': econ['KOSPI'],
        'KOSDAQ': econ['KOSDAQ'],
    }

    return JsonResponse(result)

# Selenium을 사용한 기업 개요 크롤링
def crawl_company_info(code):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    url = f"https://navercomp.wisereport.co.kr/v2/company/c1020001.aspx?cmp_cd={code}&cn="
    driver.get(url)
    time.sleep(2)

    try:
        address = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[1]/td').text.strip()
        homepage = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[2]/td[1]/a').get_attribute("href").strip()
        ceo = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[3]/td[2]').text.strip()
        establishment_date = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[3]/td[1]').text.strip()

        company_info = {
            "본사주소": address,
            "홈페이지": homepage,
            "대표이사": ceo,
            "설립일": establishment_date
        }
    except Exception as e:
        print(f"❌ 크롤링 오류: {e}")
        company_info = {}

    driver.quit()
    return company_info

# 기업별 상세페이지 뷰 (JSON 데이터 로딩 포함)
def company_detail(request, company):
    if company not in COMPANY_CODES:
        raise Http404("존재하지 않는 기업입니다.")

    base_path = os.path.join(settings.BASE_DIR, 'capstone_app', 'static', 'data_all')
    years = ['2022', '2023', '2024']
    financial_data = {}

    for year in years:
        for sheet in ['재무상태표', '포괄손익계산서']:
            file_path = os.path.join(base_path, f'{COMPANY_CODES[company]}_{year}_{sheet}.json')
            try:
                with open(file_path, encoding='utf-8') as f:
                    financial_data[f'{sheet}_{year}'] = json.load(f)
            except FileNotFoundError:
                financial_data[f'{sheet}_{year}'] = {}

    economic_index_path = os.path.join(base_path, 'economic_index.json')
    try:
        with open(economic_index_path, encoding='utf-8') as f:
            economic_index = json.load(f)
    except FileNotFoundError:
        economic_index = {}

    company_info = crawl_company_info(COMPANY_CODES[company])

    context = {
        'company_name': company,
        'company_info': company_info,
        'financial_data': financial_data,
        'economic_index': economic_index,
    }

    template_name = f"{company}.html"

    return render(request, template_name, context)

def calculate_indicators(financial_data, year):
    # financial_data는 이미 json에서 불러온 리스트 (포괄손익계산서, 재무상태표)
    # year는 문자열 '2022' 등

    # 각 재무제표에서 필요한 계정명 기준 예시 (DART 기준 계정명은 다를 수 있으니 실제 데이터 확인 필요)
    def find_value(items, name):
        for item in items:
            if item.get('account_nm') == name:
                return float(item.get('thstrm_amount', '0').replace(',', '')) if item.get('thstrm_amount') else 0
        return 0

    # 2022년 포괄손익계산서 & 재무상태표 json 리스트
    income_statement = financial_data.get(f'포괄손익계산서_{year}', [])
    balance_sheet = financial_data.get(f'재무상태표_{year}', [])

    # 기본 값들 (예시, 필요에 따라 계정명 조정)
    당기순이익 = find_value(income_statement, '당기순이익(손실)')
    영업이익 = find_value(income_statement, '영업이익(손실)')
    매출액 = find_value(income_statement, '매출액')
    자본총계 = find_value(balance_sheet, '자본총계')
    자산총계 = find_value(balance_sheet, '자산총계')
    부채총계 = find_value(balance_sheet, '부채총계')
    유동자산 = find_value(balance_sheet, '유동자산')
    유동부채 = find_value(balance_sheet, '유동부채')
    발행주식수 = find_value(balance_sheet, '자본금') / 5000  # 자본금/액면가(5,000원)로 주식수 추정 (예시)
    시가총액 = 0  # 별도 크롤링 필요 또는 주가*발행주식수 계산

    indicators = {}

    try:
        # ROE = 당기순이익 / 자본총계 * 100 (%)
        indicators['ROE'] = round(당기순이익 / 자본총계 * 100, 2) if 자본총계 else None
        # ROA = 당기순이익 / 자산총계 * 100 (%)
        indicators['ROA'] = round(당기순이익 / 자산총계 * 100, 2) if 자산총계 else None
        # 영업이익률 = 영업이익 / 매출액 * 100 (%)
        indicators['영업이익률'] = round(영업이익 / 매출액 * 100, 2) if 매출액 else None
        # 순이익률 = 당기순이익 / 매출액 * 100 (%)
        indicators['순이익률'] = round(당기순이익 / 매출액 * 100, 2) if 매출액 else None
        # 부채비율 = 부채총계 / 자본총계 * 100 (%)
        indicators['부채비율'] = round(부채총계 / 자본총계 * 100, 2) if 자본총계 else None
        # 유동비율 = 유동자산 / 유동부채 * 100 (%)
        indicators['유동비율'] = round(유동자산 / 유동부채 * 100, 2) if 유동부채 else None
        # EPS = 당기순이익 / 발행주식수
        indicators['EPS'] = round(당기순이익 / 발행주식수, 2) if 발행주식수 else None
        # BPS = 자본총계 / 발행주식수
        indicators['BPS'] = round(자본총계 / 발행주식수, 2) if 발행주식수 else None
        # PER = 주가 / EPS (주가 필요)
        indicators['PER'] = None
        # PBR = 주가 / BPS (주가 필요)
        indicators['PBR'] = None
    except Exception as e:
        print(f"투자지표 계산 중 오류: {e}")

    return indicators
