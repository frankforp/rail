from get_data.config import *

def get_timetable_thread(info):
    line, start, arrive, code, start_en, arrive_en = info.split('-|-')
    get = getjson(get_timetable_url % (code, start_en, arrive_en, tomorrow))
    data = []
    order, day, runtime = 1, 1, 0
    if not get:
        return None
    log('检索 %s 次  %s - %s  %s%%' % (line, start, arrive,
                                    int(lines_list.index(info) / len(lines_list) * 100)))
    for row in get.get('data', {}).get('data', []):
        station, arrivetime, leavetime = row['station_name'], row['arrive_time'], row['start_time']
        if arrivetime == '----': arrivetime = leavetime
        if leavetime == '----': leavetime = arrivetime
        arrivetime = datetime.strptime('1970-01-01' + arrivetime, "%Y-%m-%d%H:%M") + timedelta(days=day)
        if order == 1:
            lasttime = arrivetime
        if arrivetime < lasttime:
            arrivetime += timedelta(days=1)
            day += 1
        arrivedate = day
        leavetime = datetime.strptime('1970-01-01' + leavetime, "%Y-%m-%d%H:%M") + timedelta(days=day)
        if leavetime < arrivetime:
            leavetime += timedelta(days=1)
            day += 1
        leavedate = day
        staytime = int((leavetime - arrivetime).total_seconds() / 60)
        runtime += int((leavetime - lasttime).total_seconds() / 60)
        lasttime = leavetime
        data.append([line, code, order, station, arrivedate, arrivetime.time(), leavedate, leavetime.time(), staytime])
        order += 1
    if len(data) > 1:
        data[0][-1] = -1
        data[-1][-1] = -2
        lock.acquire()
        mysql.execute(("INSERT INTO %s() VALUE (null,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)" % timetable_table, data),
                         "UPDATE %s SET runtime='%s' WHERE code='%s'" % (line_table, runtime, code))
        lock.release()


def get_timetable(old=[]):
    global stations_cn, stations_en, lines
    stations_cn, stations_en, lines = stations_lines()
    global lines_list
    lines_list = mysql.execute(
        "SELECT line,start,arrive,code,start_en,arrive_en FROM %s WHERE runtime='0' and date='%s'" % (
            line_table, today))
    lines_list = sorted(['-|-'.join(lines) for lines in lines_list])
    if lines_list != old:
        ##uwsgi定时任务无法使用多线程
        # rs = threadpool.makeRequests(get_timetable_thread, lines_list)
        # [pool.putRequest(r) for r in rs]
        # pool.wait()
        for info in lines_list:
            get_timetable_thread(info)
        return get_timetable(lines_list)
    lines_yes, lines_all = mysql.execute(
        "SELECT code FROM %s WHERE runtime>0 and date='%s'" % (line_table, today),
        "SELECT code FROM %s GROUP BY code" % timetable_table)
    if len(lines_yes) < len(lines_all):
        lines_yes = [line[0] for line in lines_yes]
        mysql.execute("DELETE FROM %s WHERE code not in('%s')" % (timetable_table, "','".join(lines_yes)),
                         "DELETE FROM %s WHERE code not in('%s')" % (line_table, "','".join(lines_yes)))
        log('删除 车次 %s' % (len(lines_all) - len(lines_yes)))


if __name__ == '__main__':
    get_timetable()

