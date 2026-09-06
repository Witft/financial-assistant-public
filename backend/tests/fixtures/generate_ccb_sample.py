#!/usr/bin/env python3
"""Generate the deterministic, explicitly synthetic CCB XLS parser fixture.

This file deliberately implements only the small BIFF8/CFB subset required for
this test workbook. It has no runtime dependencies and never reads a bank bill.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct


OUTPUT_PATH = Path(__file__).with_name("ccb_sample.xls")
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD

# Every transaction scenario, identity, date, and amount below is invented for
# this fixture. The first row retains a real financial-organization label only
# for public parser/classification compatibility; it is not private data and
# this generator does not read or copy any original workbook or source bill.
ROWS = [
    ("20260404", "消费", -160.0, "支付宝-支付宝-理财-蚂蚁（杭州）基金销售有限公司"),
    ("20260405", "支付机构提现", -40.0, "合成测试-虚构电子钱包提现"),
    ("20260406", "信用卡卡号还款", -300.0, "合成测试-虚构信用卡还款"),
    ("20260407", "消费退货", 55.0, "合成测试-虚构商户退款"),
    ("20260408", "跨行转入", 1000.0, "资金发放"),
    ("20260409", "消费", -23.5, "合成测试-虚构咖啡店"),
    ("20260410", "跨行转出", -88.0, "合成测试-虚构收款方"),
    ("20260411", "代发工资", 6000.0, "合成测试-虚构雇主"),
    ("20260412", "现金存入", 200.0, "合成测试-虚构现金存入"),
    ("20260413", "消费", -60.0, "合成测试-虚构书店"),
    ("20260414", "消费", -9.0, "合成测试-虚构公交"),
    ("20260415", "手续费", -2.0, "合成测试-虚构服务费"),
]


def record(record_id: int, payload: bytes = b"") -> bytes:
    return struct.pack("<HH", record_id, len(payload)) + payload


def bof(stream_type: int) -> bytes:
    return record(0x0809, struct.pack("<HHHHII", 0x0600, stream_type, 0x0DBB, 0x07CC, 0, 0))


def label(row: int, column: int, value: str) -> bytes:
    encoded = value.encode("utf-16le")
    payload = struct.pack("<HHHHB", row, column, 0, len(value), 1) + encoded
    return record(0x0204, payload)


def number(row: int, column: int, value: float) -> bytes:
    return record(0x0203, struct.pack("<HHHd", row, column, 0, value))


def build_workbook_stream() -> bytes:
    # A deliberately unused large SST keeps the workbook stream over 4096 bytes,
    # allowing a simple standard FAT stream instead of a mini-stream container.
    padding_text = b"S" * 5000
    sst = record(0x00FC, struct.pack("<IIHB", 1, 1, len(padding_text), 0) + padding_text)
    global_prefix = bof(0x0005) + record(0x0042, struct.pack("<H", 1200)) + sst
    sheet_name = "Synthetic CCB"
    boundsheet_payload_size = 4 + 1 + 1 + 1 + 1 + len(sheet_name.encode("utf-16le"))
    globals_size = len(global_prefix) + 4 + boundsheet_payload_size + len(record(0x000A))
    boundsheet = record(
        0x0085,
        struct.pack("<IBBBB", globals_size, 0, 0, len(sheet_name), 1)
        + sheet_name.encode("utf-16le"),
    )

    worksheet = [
        bof(0x0010),
        record(0x0200, struct.pack("<IIHHH", 0, len(ROWS) + 3, 0, 4, 0)),
        label(0, 0, "SYNTHETIC TEST FIXTURE — NOT A REAL BANK STATEMENT"),
        label(1, 0, "All people, transaction scenarios, amounts, and dates are invented."),
        label(2, 0, "交易日期"),
        label(2, 1, "摘要"),
        label(2, 2, "交易金额"),
        label(2, 3, "交易地点/附言"),
    ]
    for row_index, (date, summary, amount, note) in enumerate(ROWS, start=3):
        worksheet.extend((label(row_index, 0, date), label(row_index, 1, summary), number(row_index, 2, amount), label(row_index, 3, note)))
    worksheet.append(record(0x000A))
    return global_prefix + boundsheet + record(0x000A) + b"".join(worksheet)


def directory_entry(name: str, entry_type: int, start_sector: int, size: int, child: int = FREESECT) -> bytes:
    entry = bytearray(128)
    name_bytes = (name + "\0").encode("utf-16le")
    entry[:len(name_bytes)] = name_bytes
    struct.pack_into("<H", entry, 64, len(name_bytes))
    entry[66] = entry_type
    entry[67] = 1
    struct.pack_into("<III", entry, 68, FREESECT, FREESECT, child)
    struct.pack_into("<I", entry, 116, start_sector)
    struct.pack_into("<Q", entry, 120, size)
    return bytes(entry)


def build_compound_file(workbook_stream: bytes) -> bytes:
    sector_size = 512
    stream_sector_count = (len(workbook_stream) + sector_size - 1) // sector_size
    fat_sector = stream_sector_count + 1

    header = bytearray(sector_size)
    header[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<H", header, 24, 0x003E)
    struct.pack_into("<H", header, 26, 3)
    struct.pack_into("<H", header, 28, 0xFFFE)
    struct.pack_into("<H", header, 30, 9)
    struct.pack_into("<H", header, 32, 6)
    struct.pack_into("<I", header, 40, 0)
    struct.pack_into("<I", header, 44, 1)
    struct.pack_into("<I", header, 48, 0)
    struct.pack_into("<I", header, 56, 4096)
    struct.pack_into("<I", header, 60, ENDOFCHAIN)
    struct.pack_into("<I", header, 68, ENDOFCHAIN)
    struct.pack_into("<I", header, 72, 0)
    difat = [fat_sector] + [FREESECT] * 108
    struct.pack_into("<109I", header, 76, *difat)

    directory = (
        directory_entry("Root Entry", 5, ENDOFCHAIN, 0, child=1)
        + directory_entry("Workbook", 2, 1, len(workbook_stream))
        + bytes(sector_size - 256)
    )
    sectors = [directory]
    padded_stream = workbook_stream + bytes(stream_sector_count * sector_size - len(workbook_stream))
    sectors.extend(padded_stream[index:index + sector_size] for index in range(0, len(padded_stream), sector_size))

    fat = [FREESECT] * 128
    fat[0] = ENDOFCHAIN
    for sector in range(1, stream_sector_count + 1):
        fat[sector] = sector + 1 if sector < stream_sector_count else ENDOFCHAIN
    fat[fat_sector] = FATSECT
    sectors.append(struct.pack("<128I", *fat))
    return bytes(header) + b"".join(sectors)


def generate() -> bytes:
    return build_compound_file(build_workbook_stream())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the checked-in fixture is deterministic")
    args = parser.parse_args()
    content = generate()
    if args.check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_bytes() != content:
            return 1
        return 0
    OUTPUT_PATH.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
