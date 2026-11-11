"""Regenerate the test fixtures from the course CSVs (run from repo root).

    python tests/fixtures/make_fixtures.py

Raw lines are copied byte-for-byte (BOM, ';', decimal comma, CRLF) so the
fixtures carry the same format quirks as the real files.

readings_faults.csv injects every row-level fault class from deck slide 17 (D19):
  F-a  Month "January" instead of 1      sensor 9,  Jan 5 00-05h
  F-b  Month "NULL"                      sensor 2,  Jan 6 00-05h
  F-c  empty sensor id                   sensor 18, Jan 6 22-23h
  F-d  wind direction out of range (412) sensor 13, Jan 5 12-14h
  F-e  duplicated day                    sensor 4,  Jan 5 (24 extra rows)
  F-f  missing day                       sensor 15, Jan 6 removed
  F-g  empty readings                    sensor 18, Jan 5 00-04h
  F-h  extreme out-of-band value (99999) sensor 11, Jan 6 09h
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DAYS = {"5", "6"}
NL = "\r\n"


def lines(name):
    raw = (ROOT / name).read_bytes().decode("utf-8")
    bom = raw.startswith("﻿")
    rows = raw.lstrip("﻿").splitlines()
    return bom, rows


def write(name, rows, bom=True):
    (OUT / name).write_bytes((("﻿" if bom else "") + NL.join(rows)).encode("utf-8"))


def main():
    bom, rows = lines("Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv")
    header, body = rows[0], [r for r in rows[1:] if r.split(";")[1] in DAYS]
    write("readings_tiny.csv", [header] + body, bom)
    write("readings_n1_tiny.csv", body, bom)

    _, acc = lines("Case_Study_Speed_Limit_AccidentsYearN_V100.csv")
    acc_body = [r for r in acc[1:] if r.split(";")[1] in DAYS][:20]
    write("accidents_tiny.csv", [acc[0]] + acc_body)

    for src, dst in [("Case_Study_Speed_Limit_Sensors_V100.csv", "sensors.csv"),
                     ("Case_Study_Speed_Limit_SensorTypes_V100.csv", "sensor_types.csv")]:
        b, r = lines(src)
        write(dst, r, b)

    faulty = []
    for r in body:
        m, d, h, mi, s, sensor, value = r.split(";")
        h = int(h)
        if sensor == "15" and d == "6":
            continue                                             # F-f
        if sensor == "9" and d == "5" and h <= 5:
            m = "January"                                        # F-a
        if sensor == "2" and d == "6" and h <= 5:
            m = "NULL"                                           # F-b
        if sensor == "13" and d == "5" and 12 <= h <= 14:
            value = "412,00"                                     # F-d
        if sensor == "18" and d == "5" and h <= 4:
            value = ""                                           # F-g
        if sensor == "11" and d == "6" and h == 9:
            value = "99999,00"                                   # F-h
        if sensor == "18" and d == "6" and h >= 22:
            sensor = ""                                          # F-c
        faulty.append(";".join([m, d, str(h), mi, s, sensor, value]))
        if sensor == "4" and d == "5":
            faulty.append(faulty[-1])                            # F-e
    write("readings_faults.csv", [header] + faulty, bom)
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
