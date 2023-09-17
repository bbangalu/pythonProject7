from flask import Flask, render_template, request, jsonify
import xml.etree.ElementTree as ET
import logging
from pyflightdata import FlightData
from datetime import datetime, timedelta, time
import asyncio
import aiohttp
import os



app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

email = os.getenv("FLIGHT_DATA_API_EMAIL")
password = os.getenv("FLIGHT_DATA_API_PASSWORD")


ENDPOINT = "http://openapi.airport.co.kr/service/rest/FlightStatusList/getFlightStatusList"
SERVICE_KEY = "3jkDYzA2uD6s50OH4zqE/NRd7uXuypkyG0gG7Rq550Dnn4nQYBcUpRKVMELmOpA3vh5vZ4n+kozC0gXkkDcWHg=="


AIRPORT_CODES = [
    {"code": "GMP", "name": "김포"},
    {"code": "CJU", "name": "제주"},
    {"code": "PUS", "name": "김해"},
    {"code": "MWX", "name": "무안"},
    {"code": "YNY", "name": "양양"},
    {"code": "CJJ", "name": "청주"},
    {"code": "TAE", "name": "대구"},
    {"code": "WJU", "name": "원주"},
    {"code": "KPO", "name": "포항경주"},
    {"code": "USN", "name": "울산"},
    {"code": "HIN", "name": "사천"},
    {"code": "KUV", "name": "군산"},
    {"code": "KWJ", "name": "광주"},
    {"code": "RSU", "name": "여수"},
]

# 항공사 코드와 로고 매핑
AIRLINE_LOGOS = {
    '4H': '4h.png',
    '4V': '4v.gif',
    '7C': '7c.png',
    'BX': 'bx.gif',
    'KE': 'ke.gif',
    'KJ': 'kj.gif',
    'LJ': 'lj.png',
    'OZ': 'oz.png',
    'RF': 'rf.jpg',
    'RS': 'rs.gif',
    'TW': 'tw.gif',
    'YO': 'yo.png',
    'ZE': 'ze.png',
    'MU': '중국동방항공.gif',
    'JL': '일본항공.gif',
    'NH': '전일본공수.gif',
    'CA': '중국국제항공.gif',
    'CZ': '중국남방항공.gif',
    'BR': '에바항공(장영항공).gif',
    'FM': '상해항공.gif',
    'IT': '타이거에어 타이완.gif',
    '9C': '춘추항공.gif',
    'HO': '중국길상항공(준야오항공).jpg',
    'UO': 'HONGKONGEXPRESS.jpg',
    'CX': '퍼시픽항공.gif',
    'CI': '중화항공.gif',
    'VJ': '비엣젯항공.gif',
    'VN': '베트남항공.gif',
    'PR': '필리핀항공.gif',
    'BL': '퍼시픽항공.gif',
    'SQ': '싱가폴항공.gif',
    'UO': '홍콩익스프레스.gif'
}

# IATA 코드를 ICAO 코드로 변환하는 함수
def iata_to_icao(iata_code):
    mapping = {
        'KE': 'KAL',
        'OZ': 'AAR',
        '7C': 'JJA',
        'LJ': 'JNA',
        'BX': 'ABL',
        'ZE': 'ESR',
        'KJ': 'AIH',
        'RS': 'ASV',
        '4V': 'FGW',
        'TW': 'TWB',
        'YP': 'APZ',
        'RF': 'EOK',
        '4H': 'HGG',
        'GJ': 'CDC',
        'UO': 'HKE',
        '9C': 'CQH'
    }
    return mapping.get(iata_code, iata_code)  # If not found, return the original IATA code


def determine_flight_status(departure_time, arrival_time):
    if departure_time not in [None, 'None'] and arrival_time not in [None, 'None']:
        return "비행 종료"
    elif departure_time not in [None, 'None'] and arrival_time in [None, 'None']:
        return "비행 중"
    else:
        return "출발 전"



async def get_data(airport_code, flight_type):
    async with aiohttp.ClientSession() as session:
        departures, arrivals = await fetch_flight_info(session, airport_code=airport_code, flight_type=flight_type)
    return departures, arrivals

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_airport = "USN"
    flight_type = request.form.get('flight_type') or request.args.get('flight_type', 'D')
    show_all = request.args.get('show_all', 'true')

    if request.method == 'POST':
        selected_airport = request.form.get('airport_code')
        print(f"Selected Airport: {selected_airport}")
    elif 'airport_code' in request.args:
        selected_airport = request.args.get('airport_code')

    # 항상 최신 정보를 가져오기 위해 API를 호출
    loop = asyncio.new_event_loop()
    departures, arrivals = loop.run_until_complete(get_data(airport_code=selected_airport, flight_type=flight_type))

    mark_flights_in_air(departures, arrivals, selected_airport)

    if flight_type == "I":  # 국제선이 선택된 경우
        flight_data_api = FlightData()

        # 로그인 시도
        try:
            flight_data_api.login(email, password)
        except Exception as e:
            print(f"An error occurred during login: {e}")

        current_date = datetime.now().strftime('%Y%m%d')

        for flight in departures + arrivals:
            flight_number = flight['airFln']
            flight_history = flight_data_api.get_flight_for_date(flight_number, current_date)

            if flight_history:
                time_data = flight_history[0].get('time', {})
                real_data = time_data.get('real', {})
                departure_time = real_data.get('departure_time')
                arrival_time = real_data.get('arrival_time')

                flight_status = determine_flight_status(departure_time, arrival_time)
                flight['flying2'] = flight_status

                if flight_status == "비행 중":
                    airline_icao = iata_to_icao(flight['airFln'][:2])
                    flight_icao_number = flight['airFln'][2:]
                    flight['flight_link'] = f"https://www.flightradar24.com/{airline_icao}{flight_icao_number}"
                else:
                    flight['flying2'] = "비행 종료"


    if show_all == 'false':
        departures = [flight for flight in departures if flight['flying2'] != '비행 종료']
        arrivals = [flight for flight in arrivals if flight.get('flying2') != '비행 종료']

    # 선택된 공항의 이름을 가져옵니다.
    selected_airport_name = next((airport["name"] for airport in AIRPORT_CODES if airport["code"] == selected_airport), "")
    # 현재 시간을 가져옵니다.

    #current_time = datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S') # 실행오류 있음
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # 실행오류 없음

    return render_template('index.html', flight_type=flight_type, departures=departures, arrivals=arrivals,
                           AIRPORT_CODES=AIRPORT_CODES, selected_airport=selected_airport, AIRLINE_LOGOS=AIRLINE_LOGOS,
                           selected_airport_name=selected_airport_name, current_time=current_time, show_all=show_all)






@app.route('/get_airlines', methods=['GET'])
def get_airlines():
    airport_code = request.args.get('airport_code', "USN")
    departures, _ = fetch_flight_info(airport_code)
    if not departures:
        return jsonify({"error": "Failed to fetch airlines"}), 500

    airlines = list(set([(iata_to_icao(flight['airFln'][:2]), flight['airlineKorean']) for flight in departures]))
    return jsonify({"airlines": [{"airlineCode": code, "airlineName": name} for code, name in airlines]})


@app.route('/fetch_info', methods=['GET'])
def fetch_info():
    airport_code = request.args.get('airport_code', "USN")
    airline_name = request.args.get('airline_name', None)  # airline_name으로 변경
    departures, arrivals = fetch_flight_info(airport_code)
    if not departures or not arrivals:
        return jsonify({"error": "Failed to fetch flight info"}), 500

    if airline_name and airline_name != "all":
        departures = [flight for flight in departures if flight['airlineKorean'] == airline_name]  # airlineKorean 필드 사용
        arrivals = [flight for flight in arrivals if flight['airlineKorean'] == airline_name]  # airlineKorean 필드 사용

    mark_flights_in_air(departures, arrivals, airport_code)
    return jsonify({
        "departures": departures,
        "arrivals": arrivals
    })


def get_airport_code_from_name(airport_name):
    airport_name_to_code = {
        '서울/김포': 'GMP',
        '부산/김해': 'PUS',
        '제주': 'CJU',
        '무안': 'MWX',
        '양양': 'YNY',
        '청주': 'CJJ',
        '대구': 'TAE',
        '원주': 'WJU',
        '포항/포항경주': 'KPO',
        '울산': 'USN',
        '진주/사천': 'HIN',
        '군산': 'KUV',
        '광주': 'KWJ',
        '여수': 'RSU',
    }
    code = airport_name_to_code.get(airport_name)
    if code is None:
        logging.warning(f"Airport name not found in dictionary: {airport_name}")
    return code


async def fetch_flight_info(session, airport_code="USN", flight_type="D"):
    params = {
        "ServiceKey": SERVICE_KEY,
        "schAirCode": airport_code,
        "schLineType": flight_type,
        "numOfRows": 1000
    }
    async with session.get(ENDPOINT, params=params) as response:
        if response.status != 200:
            logging.error(f"API request failed with status code {response.status}. Response: {response.text}")
            return [], []

        content = await response.text()
        root = ET.fromstring(content)

        departures = []
        arrivals = []

        for item in root.findall(".//item"):
            flight_data = {
                "airFln": item.find("airFln").text if item.find("airFln") is not None else "",
                "airlineKorean": item.find("airlineKorean").text if item.find("airlineKorean") is not None else "",
                "airlineEnglish": item.find("airlineEnglish").text if item.find("airlineEnglish") is not None else "",
                "boardingKor": item.find("boardingKor").text if item.find("boardingKor") is not None else "",
                "boardingEng": item.find("boardingEng").text if item.find("boardingEng") is not None else "",
                "arrivedKor": item.find("arrivedKor").text if item.find("arrivedKor") is not None else "",
                "arrivedEng": item.find("arrivedEng").text if item.find("arrivedEng") is not None else "",
                "std": item.find("std").text if item.find("std") is not None else "",
                "etd": item.find("etd").text if item.find("etd") is not None else "-",
                "rmkKor": item.find("rmkKor").text if item.find("rmkKor") is not None else "",
                "gate": item.find("gate").text if item.find("gate") is not None else "-",
                "flying": ""  # 비행 중 상태를 저장할 새로운 필드
            }

            if item.find("io").text == "O":
                departures.append(flight_data)
            else:
                arrivals.append(flight_data)

    return departures, arrivals


async def fetch_all_flight_info_for_airports():
    all_flights_info = {}
    async with aiohttp.ClientSession() as session:
        for airport in AIRPORT_CODES:
            departures, arrivals = await fetch_flight_info(session, airport["code"])
            all_flights_info[airport["code"]] = (departures, arrivals)
    return all_flights_info


def parse_time(time_str):
    try:
        # 'HHMM' 형식으로 시간과 분을 파싱합니다.
        parsed_time = time(int(time_str[:2]), int(time_str[2:]))

        # 현재 날짜의 연, 월, 일 정보를 가져옵니다.
        current_date = datetime.now()

        # 현재 날짜의 연, 월, 일 정보와 파싱된 시간 정보를 결합하여 datetime 객체를 생성합니다.
        return datetime.combine(current_date.date(), parsed_time)
    except ValueError:
        # 실패하면 현재 시간을 반환합니다.
        return datetime.now()


def mark_flights_in_air(departures, arrivals, selected_airport):
    # Fetch flight info for all airports in advance
    loop = asyncio.new_event_loop()
    all_flights_info = loop.run_until_complete(fetch_all_flight_info_for_airports())


    # 도착 정보 필터링
    current_time = datetime.now()

    # 도착 정보 필터링
    arrivals = [flight for flight in arrivals if not (
            (parse_time(flight.get('std', '0000')) < current_time - timedelta(hours=1)) and
            (flight.get('rmkKor') != '도착')
    )]

    # 출발 정보 필터링
    departures = [flight for flight in departures if not (
            (flight.get('rmkKor') == '출발') and
            (parse_time(flight.get('std', '0000')) > current_time + timedelta(hours=1))
    )]



    # Handle arrivals
    for arrival in arrivals:
        # 기본 값을 "정보없음"으로 설정
        arrival['flying2'] = "정보없음"

        origin_airport_name = arrival['boardingKor']
        origin_airport_code = get_airport_code_from_name(origin_airport_name)

        if origin_airport_code is None:  # 국제선 도착 정보
            continue

        all_departures_for_origin = all_flights_info[origin_airport_code][0]  # Only need departure info

        matching_departure = next(
            (departure for departure in all_departures_for_origin if departure['airFln'] == arrival['airFln']), None)

        if matching_departure:
            arrival['flying'] = matching_departure['rmkKor']
            if arrival['flying'] == "출발":
                arrival['flying2'] = "비행 중"
                airline_icao = iata_to_icao(arrival['airFln'][:2])
                flight_icao_number = arrival['airFln'][2:]
                arrival['flight_link'] = f"https://www.flightradar24.com/{airline_icao}{flight_icao_number}"
            else:
                arrival['flying2'] = "출발 전"

        if not arrival['rmkKor'] and arrival['flying'] == "출발":
            arrival['flying2'] = "비행 중"
            airline_icao = iata_to_icao(arrival['airFln'][:2])
            flight_icao_number = arrival['airFln'][2:]
            arrival['flight_link'] = f"https://www.flightradar24.com/{airline_icao}{flight_icao_number}"

        elif not arrival['rmkKor']:
            arrival['flying2'] = "출발 전"
        elif arrival['rmkKor'] == "도착":
            arrival['flying2'] = "비행 종료"

    # Handle departures
    for departure in departures:
        # 기본 값을 "정보없음"으로 설정
        departure['flying2'] = "정보없음"

        destination_airport_name = departure['arrivedKor']
        destination_airport_code = get_airport_code_from_name(destination_airport_name)

        if destination_airport_code is None:  # 국제선 출발 정보
            continue

        all_arrivals_for_destination = all_flights_info[destination_airport_code][1]  # Only need arrival info

        matching_arrival = next(
            (arrival for arrival in all_arrivals_for_destination if arrival['airFln'] == departure['airFln']), None)

        if matching_arrival:
            departure['flying'] = matching_arrival['rmkKor']

        if departure['rmkKor'] == "출발" and departure['flying'] == "도착":
            departure['flying2'] = "비행 종료"
        elif departure['rmkKor'] == "출발" and departure['flying'] != "도착":
            departure['flying2'] = "비행 중"
            airline_icao = iata_to_icao(departure['airFln'][:2])
            flight_icao_number = departure['airFln'][2:]
            departure['flight_link'] = f"https://www.flightradar24.com/{airline_icao}{flight_icao_number}"

        elif departure['rmkKor'] != "출발":
            departure['flying2'] = "출발 전"

if __name__ == '__main__':
    app.run(debug=True)
