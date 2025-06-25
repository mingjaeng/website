import os
import json
import time

from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import render
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

COMPANY_CODES = {
    "데브시스터즈": "194480",
    "한선엔지니어링": "060560",
    "고려제강": "002240",
    "메카로": "089010",
    "셀바스캔": "208370",
    "성우하이텍": "015750",
}

def home_redirect(request):
    return render(request, 'index.html')

def home(request):
    return render(request, 'index.html')

def get_stock_code(company_name):
    search_url = f"https://finance.naver.com/search/searchList.naver?query={company_name}"
    res = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(res.text, 'html.parser')
    a_tag = soup.select_one('ul.searchList li a')
    if a_tag and 'code=' in a_tag.get('href'):
        return a_tag['href'].split('code=')[-1]
    return None

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

def get_economic_indicators():
    indicators = {}
    try:
        res = requests.get('https://finance.naver.com/marketindex/', headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        indicators['USD_KRW'] = soup.select_one('div.market1 span.value').text.strip()
    except:
        indicators['USD_KRW'] = None

    try:
        res2 = requests.get('https://finance.naver.com/sise/', headers={'User-Agent': 'Mozilla/5.0'})
        soup2 = BeautifulSoup(res2.text, 'html.parser')
        indicators['KOSPI'] = soup2.select_one('#KOSPI_now').text.strip()
        indicators['KOSDAQ'] = soup2.select_one('#KOSDAQ_now').text.strip()
    except:
        indicators['KOSPI'] = indicators['KOSDAQ'] = None

    return indicators

def crawl_company_info(code):
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    url = f"https://navercomp.wisereport.co.kr/v2/company/c1020001.aspx?cmp_cd={code}"
    driver.get(url)
    time.sleep(2)

    try:
        address = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[1]/td').text.strip()
        homepage = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[2]/td[1]/a').get_attribute("href").strip()
        ceo = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[3]/td[2]').text.strip()
        establishment_date = driver.find_element(By.XPATH, '//*[@id="cTB201"]/tbody/tr[3]/td[1]').text.strip()
        listed_date = ""

        if "(상장일:" in establishment_date:
            parts = establishment_date.split("(상장일:")
            establishment_date = parts[0].strip()
            listed_date = parts[1].replace(")", "").strip()

        industry_url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(industry_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        industry = ""
        try:
            trade_section = soup.select_one("div.trade_compare em")
            if trade_section:
                a_tag = trade_section.find("a")
                if a_tag:
                    industry = a_tag.text.strip()               
        except Exception as e:
            print("[업종명 크롤링 오류]", e)
            industry = ""

        return {
            "본사주소": address,
            "홈페이지": homepage,
            "대표이사": ceo,
            "설립일": establishment_date,
            "상장일": listed_date,
            "업종명": industry
        }
    except Exception as e:
        print("[크롤링 오류]", e)
        return {}
    finally:
        driver.quit()

def parse_float_safe(val):
    try:
        if val == "--":
            return None
        return float(val)
    except:
        return None
    
# 수익성 지표 계산 함수
def calculate_profitability_indicators(bs_data, is_data, cf_data, years):
    result = {
        "매출총이익률": {},
        "영업이익률": {},
        "순이익률": {},
        "EBITDA마진율": {},
        "ROE": {},
        "ROA": {},
        "ROIC": {}
    }

    for year in years:
        try:
            sales = parse_float_safe(is_data.get("매출액", {}).get(year))
            gross_profit = parse_float_safe(is_data.get("매출총이익", {}).get(year))
            op_profit = parse_float_safe(is_data.get("영업이익(손실)", {}).get(year))
            net_profit = parse_float_safe(is_data.get("당기순이익(손실)", {}).get(year))
            depreciation = parse_float_safe(cf_data.get("감가상각비", {}).get(year))
            total_equity = parse_float_safe(bs_data.get("자본총계", {}).get(year))
            total_assets = parse_float_safe(bs_data.get("자산총계", {}).get(year))
            total_liabilities = parse_float_safe(bs_data.get("부채총계", {}).get(year))

            tax_rate = 0.25
            nopat = op_profit * (1 - tax_rate) if op_profit is not None else None
            invested_capital = (total_liabilities or 0) + (total_equity or 0)

            result["매출총이익률"][year] = round(gross_profit / sales * 100, 2) if sales and gross_profit else "--"
            result["영업이익률"][year] = round(op_profit / sales * 100, 2) if sales and op_profit else "--"
            result["순이익률"][year] = round(net_profit / sales * 100, 2) if sales and net_profit else "--"
            result["EBITDA마진율"][year] = round((op_profit + depreciation) / sales * 100, 2) if sales and op_profit is not None and depreciation is not None else "--"
            result["ROE"][year] = round(net_profit / total_equity * 100, 2) if net_profit and total_equity else "--"
            result["ROA"][year] = round(net_profit / total_assets * 100, 2) if net_profit and total_assets else "--"
            result["ROIC"][year] = round(nopat / invested_capital * 100, 2) if nopat and invested_capital else "--"

        except Exception as e:
            print(f"[Error: {year}] {e}")
            continue

    return result

# 안정성 지표 계산 함수
def calculate_stability_indicators(bs_data, is_data, cf_data, years):
    result = {
        "부채비율": {},
        "유동부채비율": {},
        "비유동부채비율": {},
        "순부채비율": {},
        "유동비율": {},
        "당좌비율": {},
        "이자보상배율": {},
        "금융비용부담률": {},
        "자본유보율": {},
    }

    for year in years:
        try:
            total_liabilities = float(bs_data.get("부채총계", {}).get(year, 0))
            current_liabilities = float(bs_data.get("유동부채", {}).get(year, 0))
            non_current_liabilities = float(bs_data.get("비유동부채", {}).get(year, 0))
            total_equity = float(bs_data.get("자본총계", {}).get(year, 0))
            current_assets = float(bs_data.get("유동자산", {}).get(year, 0))
            inventory = float(bs_data.get("재고자산", {}).get(year, 0))
            cash_equivalents = float(bs_data.get("현금및현금성자산", {}).get(year, 0))
            retained_earnings = float(bs_data.get("이익잉여금", {}).get(year, 0))
            capital_stock = float(bs_data.get("자본금", {}).get(year, 0))

            op_profit = float(is_data.get("영업이익(손실)", {}).get(year, 0))
            interest_expense = float(is_data.get("금융원가", {}).get(year, 0))
            sales = float(is_data.get("매출액", {}).get(year, 0))

            net_debt = total_liabilities - cash_equivalents

            result["부채비율"][year] = round(total_liabilities / total_equity * 100, 2) if total_equity else None
            result["유동부채비율"][year] = round(current_liabilities / total_liabilities * 100, 2) if total_liabilities else None
            result["비유동부채비율"][year] = round(non_current_liabilities / total_liabilities * 100, 2) if total_liabilities else None
            result["순부채비율"][year] = round(net_debt / total_equity * 100, 2) if total_equity else None
            result["유동비율"][year] = round(current_assets / current_liabilities * 100, 2) if current_liabilities else None
            result["당좌비율"][year] = round((current_assets - inventory) / current_liabilities * 100, 2) if current_liabilities else None
            result["이자보상배율"][year] = round(op_profit / interest_expense, 2) if interest_expense else None
            result["금융비용부담률"][year] = round(interest_expense / sales * 100, 2) if sales else None
            result["자본유보율"][year] = round(retained_earnings / capital_stock * 100, 2) if capital_stock else None

        except Exception as e:
            print(f"[안정성 지표 오류: {year}] {e}")
            continue

    return result

# 성장성 지표 계산 함수
def calculate_growth_indicators(bs_data, is_data, cf_data, years):
    result = {
        "매출액증가율": {},
        "영업이익증가율": {},
        "순이익증가율": {},
        "총자산증가율": {},
        "유동자산증가율": {},
        "유형자산증가율": {},
        "자기자본증가율": {},
    }

    for i in range(1, len(years)):
        prev = years[i]
        curr = years[i - 1]
        try:
            sales_curr = float(is_data.get("매출액", {}).get(curr, 0))
            sales_prev = float(is_data.get("매출액", {}).get(prev, 0))
            op_curr = float(is_data.get("영업이익(손실)", {}).get(curr, 0))
            op_prev = float(is_data.get("영업이익(손실)", {}).get(prev, 0))
            net_curr = float(is_data.get("당기순이익(손실)", {}).get(curr, 0))
            net_prev = float(is_data.get("당기순이익(손실)", {}).get(prev, 0))

            total_assets_curr = float(bs_data.get("자산총계", {}).get(curr, 0))
            total_assets_prev = float(bs_data.get("자산총계", {}).get(prev, 0))
            current_assets_curr = float(bs_data.get("유동자산", {}).get(curr, 0))
            current_assets_prev = float(bs_data.get("유동자산", {}).get(prev, 0))
            tangible_assets_curr = float(bs_data.get("유형자산", {}).get(curr, 0))
            tangible_assets_prev = float(bs_data.get("유형자산", {}).get(prev, 0))
            equity_curr = float(bs_data.get("자본총계", {}).get(curr, 0))
            equity_prev = float(bs_data.get("자본총계", {}).get(prev, 0))

            result["매출액증가율"][curr] = round((sales_curr - sales_prev) / sales_prev * 100, 2) if sales_prev else None
            result["영업이익증가율"][curr] = round((op_curr - op_prev) / op_prev * 100, 2) if op_prev else None
            result["순이익증가율"][curr] = round((net_curr - net_prev) / net_prev * 100, 2) if net_prev else None
            result["총자산증가율"][curr] = round((total_assets_curr - total_assets_prev) / total_assets_prev * 100, 2) if total_assets_prev else None
            result["유동자산증가율"][curr] = round((current_assets_curr - current_assets_prev) / current_assets_prev * 100, 2) if current_assets_prev else None
            result["유형자산증가율"][curr] = round((tangible_assets_curr - tangible_assets_prev) / tangible_assets_prev * 100, 2) if tangible_assets_prev else None
            result["자기자본증가율"][curr] = round((equity_curr - equity_prev) / equity_prev * 100, 2) if equity_prev else None

        except Exception as e:
            print(f"[성장성 지표 오류: {curr}] {e}")
            continue

    return result

# 가치평가 지표 계산 함수
def calculate_valuation_indicators(bs_data, is_data, cf_data, years):
    result = {
        "EPS": {},
        "BPS": {},
        "CPS": {},
        "SPS": {},
        "DPS": {},
        "PER": {},
        "PBR": {},
        "PCR": {},
        "PSR": {},
        "EV/EBITDA": {},
        "현금배당수익률": {},
        "현금배당성향(%)": {},
    }

    for year in years:
        try:
            net_profit = float(is_data.get("당기순이익(손실)", {}).get(year, 0))
            total_equity = float(bs_data.get("자본총계", {}).get(year, 0))
            capital_stock = float(bs_data.get("자본금", {}).get(year, 0))
            shares = capital_stock / 5000 if capital_stock else 0

            cashflow_op = float(cf_data.get("영업활동으로인한현금흐름", {}).get(year, 0))
            sales = float(is_data.get("매출액", {}).get(year, 0))
            dividends = float(is_data.get("현금배당총액", {}).get(year, 0))
            ebitda = float(is_data.get("EBITDA", {}).get(year, 0)) or 0
            market_cap = None  # PER, PBR, PCR, PSR, EV/EBITDA 계산 시 주가 필요

            # 주당 계산 (주가 기반 제외)
            result["EPS"][year] = round(net_profit / shares, 2) if shares else None
            result["BPS"][year] = round(total_equity / shares, 2) if shares else None
            result["CPS"][year] = round(cashflow_op / shares, 2) if shares else None
            result["SPS"][year] = round(sales / shares, 2) if shares else None
            result["DPS"][year] = round(dividends / shares, 2) if shares else None

            # 주가 기반 지표는 None
            result["PER"][year] = None
            result["PBR"][year] = None
            result["PCR"][year] = None
            result["PSR"][year] = None
            result["EV/EBITDA"][year] = None

            # 배당률 계산 (수익률과 성향)
            result["현금배당수익률"][year] = None
            result["현금배당성향(%)"][year] = round(dividends / net_profit * 100, 2) if net_profit else None

        except Exception as e:
            print(f"[가치평가지표 오류: {year}] {e}")
            continue

    return result

def company_detail(request, company_name):
    if company_name not in COMPANY_CODES:
        raise Http404("존재하지 않는 기업입니다.")

    base_path = os.path.join(settings.BASE_DIR, 'capstone_app', 'static', 'data_all', '재무제표_json', company_name)
    raw_years = ['2022', '2023', '2024']
    display_years = list(reversed(raw_years))

    # 📊 재무제표 로딩 및 구성
    financial_data = {}
    for sheet in ['재무상태표', '포괄손익계산서', '현금흐름표']:
        file_path = os.path.join(base_path, f"{company_name}_{sheet}.json")
        if not os.path.exists(file_path):
            continue

        with open(file_path, encoding='utf-8') as f:
            raw = json.load(f)

        for year in raw_years:
            key = f"{sheet}_{year}".replace(" ", "").strip()
            financial_data[key] = []
            for label, values in raw.items():
                if label == "label_ko":
                    continue
                try:
                    value = values.get(year, "--")
                    value_str = str(value).strip()

                    if value_str in ("-", "--"):
                        formatted = "--"
                    else:
                        formatted_float = float(value_str.replace(",", ""))
                        formatted = round(formatted_float / 1e8, 2)
                        if formatted == 0.0:
                            formatted = 0.0
                except Exception:
                    formatted = "--"

                financial_data[key].append({
                    "account_nm": label,
                    "thstrm_amount": formatted
                })

    # 📅 연도 추출 (지표 계산용)
    bs_data = json.load(open(os.path.join(base_path, f"{company_name}_재무상태표.json"), encoding='utf-8'))
    is_data = json.load(open(os.path.join(base_path, f"{company_name}_포괄손익계산서.json"), encoding='utf-8'))
    cf_data = json.load(open(os.path.join(base_path, f"{company_name}_현금흐름표.json"), encoding='utf-8'))

    # ⛳ 연도 교집합 추출 (감가상각비는 optional 처리)
    years = list(set(bs_data.get("자산총계", {}).keys()) & set(is_data.get("매출액", {}).keys()))
    years.sort(reverse=True)

    # 📐 지표 계산
    profitability = calculate_profitability_indicators(bs_data, is_data, cf_data, years)
    stability = calculate_stability_indicators(bs_data, is_data, cf_data, years)
    growth = calculate_growth_indicators(bs_data, is_data, cf_data, years)
    valuation = calculate_valuation_indicators(bs_data, is_data, cf_data, years)

    # 🌐 경제지표
    economic_path = os.path.join(settings.BASE_DIR, 'capstone_app', 'static', 'data_all', 'economic_index.json')
    try:
        with open(economic_path, encoding='utf-8') as f:
            original_econ = json.load(f)
            economic_index = {
                "USD_KRW": original_econ.get("USD/KRW"),
                "KOSPI": original_econ.get("KOSPI"),
                "KOSDAQ": original_econ.get("KOSDAQ"),
            }
    except FileNotFoundError:
        economic_index = {}

    # 🧾 기업 일반정보
    company_info = crawl_company_info(COMPANY_CODES[company_name])

    return render(request, "company_detail.html", {
        'company_name': company_name,
        'company_info': company_info,
        'financial_data': financial_data,
        'economic_index': economic_index,
        'profitability': profitability,
        'stability': stability,
        'growth': growth,
        'valuation': valuation,
        'years': display_years,
    })


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
        'USD_KRW': econ['USD_KRW'],
        'KOSPI': econ['KOSPI'],
        'KOSDAQ': econ['KOSDAQ'],
    }
    return JsonResponse(result)



