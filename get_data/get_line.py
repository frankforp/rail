from get_data.config import *
from get_data.get_ticket import *
from get_data.get_timetable import *

def insert_station(name, code, start_en, arrive_en):
    get = getjson(get_timetable_url % (code, start_en, arrive_en, tomorrow))
    data = get.get('data', {}).get('data', [{'station_name': name + start_en}, {'station_name': name + arrive_en}])
    for en, cn in {start_en: data[0]['station_name'], arrive_en: data[-1]['station_name']}.items():
        if cn not in stations_cn:
            stations_cn[cn] = en
            stations_en[en] = cn
            log('插入 %s 站' % cn)
            mysql_db.execute("INSERT INTO %s VALUE (null,'%s','%s','%s','%s','%s','%s','%s','%s')" % (
                station_table, cn, en, 125, 30, None, None, None, today))


def get_city_line_thread(city):
    data, update_city, update_line, sqls = [], [], [], []
    start, arrive = city.split('-')
    if start not in stations_cn or arrive not in stations_cn:
        return None
    for line in get_ticket(start, arrive, tomorrow, ticker=False):
        name, code, start_en, arrive_en = line
        if start_en not in stations_en or arrive_en not in stations_en:
            insert_station(name, code, start_en, arrive_en)
        start_cn, arrive_cn = stations_en[start_en], stations_en[arrive_en]
        if code in lines:
            if lines[code] < today:
                update_line.append(code)
                lines[code] = today, today
        else:
            data.append((name, code, start_cn, start_en, arrive_cn, arrive_en, 0, today))
            lines[code] = today
    sqls.append(("INSERT INTO %s VALUE (null,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)" % line_table, data))
    sqls.append("UPDATE %s SET date='%s' WHERE code='%s'" % (line_table, today, "' or code='".join(update_line)))
    if data + update_line != []:
        log('检索 %s - %s  %s%%' % (start, arrive,
                                  int(citys_list.index(city) / len(citys_list) * 100)))
    lock.acquire()
    mysql_db.execute(*sqls)
    lock.release()


def get_city(citys):
    global citys_list
    citys_list = sorted([city for city in citys], key=lambda city: citys[city], reverse=True)
    # rs = threadpool.makeRequests(get_city_line_thread, citys_list)
    # [pool.putRequest(r) for r in rs]
    # pool.wait()
    for citys in citys_list:
        get_city_line_thread(citys)
    log('检索 城市 %s 对' % len(citys_list))


def get_line():
    global stations_cn, stations_en, lines
    stations_cn, stations_en, lines = stations_lines()
    html = requests.get(get_lines_url, verify=False).text
    get = re.findall('"%s":.+?}]}' % tomorrow, html)
    if get == []:
        data = re.findall(r'([\u4e00-\u9fa5\s]+-[\u4e00-\u9fa5\s]+)', html)
        citys = {}
        for city in set(data):
            citys[city] = data.count(city)
        get_city(citys)
    else:
        data, update_line = [], []
        for line in re.findall('{"station_train_code":"([^\)]+)\(([^-]+)-([^\)]+)\)","train_no":"([^\"]+)"}', get[0]):
            name, start, arrive, code = line
            if start not in stations_cn or arrive not in stations_cn:
                continue
            if code in lines:
                if lines[code] < today:
                    update_line.append(code)
                    lines[code] = today
            else:
                data.append((name, code, start, stations_cn[start], arrive, stations_cn[arrive], 0, today))
                lines[code] = today
        mysql_db.execute(
            ("INSERT INTO %s VALUE (null,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)" % line_table, data),
            "UPDATE %s SET date='%s' WHERE code='%s'" % (line_table, today, "' or code='".join(update_line)))
        log('插入 车次 %s ' % len(data))
        log('更新 车次 %s ' % len(update_line))


if __name__ == '__main__':
    get_line()
