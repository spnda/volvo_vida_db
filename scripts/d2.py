#!/usr/bin/env python3
"""
Volvo D2 diagnostics over CAN, as VIDA uses it for P1/P2 era cars through the DiCE.

The functions below name the VIDA classes they came from. In short:

 - Requests are 29-bit frames on CAN ID 0x000FFFFE with 8 data bytes, padded with 0x00.
 - A D2 message is the ECU address followed by the service bytes, e.g. 50 A6 1A 04 01 (CEM, Read Current Data By
   Identifier 0x1A04, send once). It is split into chunks of 7 bytes, each prefixed with a format byte:
        single frame         0xC8 + number of bytes in the frame (including the ECU address)
        first frame          0x8F
        consecutive frames   0x08 + (frame number - 1) % 8, counting frames from 1
        last frame           0x48 + number of bytes in the frame
 - ECUs answer on their own CAN ID. VIDA does not know these IDs: it accepts every frame with an odd 29-bit ID and
   identifies the ECU by the address in the second byte of single and first frames. This came from
   Vcc.Vida.DiagSwdl.VehCom2.J2534.Swdl.J2534TesterFilter (pass filter with mask and pattern 0x00000001) and
   Vcc.Vida.DiagSwdl.VehCom2.J2534.Diagnostics.D2ResponseInterpreter.
 - A positive response uses the request service + 0x40 (A6 -> E6), 0x7F is a negative response
   [0x7F, service, code] and 0x7E a general response (busy, request repeated).
 - While a session is open, VIDA sends D8 00 00 00 00 00 00 00 every 4 seconds as keep-alive. This came from
   Vcc.Vida.DiagSwdl.VehCom2.J2534.Diagnostics.DiagnosticSessionKeeper.
"""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from evaluate_conversion import parse_conversion, evaluate_ast

REQUEST_CAN_ID = 0x000FFFFE
# Not part of VIDA. Seen in CEM and ECM responses captured by others, e.g.
# https://jan-jansen.readthedocs.io/en/latest/volvo-diagnostic.html
DEFAULT_RESPONSE_CAN_ID = 0x01200021
KEEP_ALIVE = bytes([0xD8, 0, 0, 0, 0, 0, 0, 0])
KEEP_ALIVE_PERIOD_MS = 4000
NEGATIVE_RESPONSE = 0x7F
GENERAL_RESPONSE = 0x7E

# Identifier block type -> (read service, number of identifier bytes, whether a mode byte follows the identifier).
# These are the services the VIDA scripts use to read each identifier type from D2 ECUs: the read attribute of their
# <identifier> elements (T111_Service ids 4, 9, 2, 30 and 23).
READ_SERVICES = {
    'REID': (0xA6, 2, True),    # Read Current Data By Identifier
    'REOFF': (0xA5, 1, True),   # Read Current Data By Offset
    'BLOFF': (0xB9, 1, False),  # Read Data Block By Offset
    'ADDR': (0xA7, 3, True),    # Read Current Data By Address
    'RTOFF': (0xB2, 1, False),  # Control Routine By Offset
}
# Positive response service -> identifier block type
RESPONSE_TYPES = {service + 0x40: block_type for block_type, (service, _, _) in READ_SERVICES.items()}

# What evaluating a VIDA scaling expression can raise, e.g. for a division by zero
EXPRESSION_ERRORS = (ArithmeticError, ValueError, TypeError, KeyError)

# Service names from T111_Service
SERVICE_NAMES = {
    0xA0: 'Stop Diagnostic Session', 0xA1: 'No Operation Performed', 0xA3: 'Security Access',
    0xA5: 'Read Current Data By Offset', 0xA6: 'Read Current Data By Identifier', 0xA7: 'Read Current Data By Address',
    0xA8: 'Set Data Transmission', 0xA9: 'Stop Data Transmission', 0xAB: 'Read Freeze Frame Data By Offset',
    0xAC: 'Read Freeze Frame', 0xAD: 'Read Freeze Frame By DTC', 0xAE: 'Read DTC', 0xAF: 'Clear DTC',
    0xB0: 'Input Output Control By Offset', 0xB1: 'Input Output Control By Identifier',
    0xB2: 'Control Routine By Offset', 0xB8: 'Write Data Block By Offset', 0xB9: 'Read Data Block By Offset',
    0xBA: 'Write Data By Offset', 0xBB: 'Write Data By Identifier',
}


# ---------------------------------------------------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------------------------------------------------

def split_message(message: bytes) -> list[bytes]:
    """
    Splits a D2 message (ECU address + service bytes) into 8 byte CAN frames. This came from
    Vcc.Vida.DiagSwdl.VehCom2.J2534.Diagnostics.D2.D2MessageDivider and FormatByteCalculator.
    """
    chunks = [message[i:i + 7] for i in range(0, len(message), 7)]
    frames = []
    for number, chunk in enumerate(chunks, start=1):
        if len(chunks) == 1:
            fmt = 0xC8 + len(chunk)
        elif number == 1:
            fmt = 0x8F
        elif number == len(chunks):
            fmt = 0x48 + len(chunk)
        else:
            fmt = 0x08 + (number - 1) % 8
        frames.append(bytes([fmt]) + chunk.ljust(7, b'\0'))
    return frames


@dataclass
class D2Message:
    can_id: int
    address: int  # -1 for the keep-alive frame, which carries no address
    payload: bytes
    timestamp: Optional[float] = None

    @property
    def service(self) -> int:
        return self.payload[0] if self.payload else -1


class D2Reassembler:
    """
    Joins the CAN frames of D2 messages back together. Frames are tracked per CAN ID, so requests and responses
    can be fed in the order they appear on the bus. This came from ReadReply and ParseMultipleCanFrame in
    Vcc.Vida.DiagSwdl.VehCom2.J2534.Diagnostics.D2onCanApplicationDICE.
    """

    def __init__(self):
        self._pending: dict[int, dict] = {}

    def feed(self, can_id: int, data: bytes, timestamp: Optional[float] = None) -> Optional[D2Message]:
        """
        Returns the complete message when the last frame of a message arrives, otherwise None.
        """
        if len(data) < 2:
            return None
        fmt = data[0]
        kind = fmt & 0xC0
        if kind == 0xC0:  # single frame, the byte count includes the address
            self._pending.pop(can_id, None)
            length = fmt & 0x07
            if length == 0:
                return D2Message(can_id, -1, b'', timestamp)
            return D2Message(can_id, data[1], bytes(data[2:1 + length]), timestamp)
        if kind == 0x80:  # first frame
            self._pending[can_id] = {'address': data[1], 'payload': bytearray(data[2:8]), 'sequence': 1,
                                     'timestamp': timestamp}
            return None
        state = self._pending.get(can_id)
        if state is None:
            return None
        if kind == 0x00:  # consecutive frame
            if (fmt & 0x07) != state['sequence']:
                # A frame was lost, drop the message like VIDA does.
                del self._pending[can_id]
                return None
            state['sequence'] = (state['sequence'] + 1) % 8
            state['payload'] += data[1:8]
            return None
        del self._pending[can_id]  # last frame
        state['payload'] += data[1:1 + (fmt & 0x07)]
        return D2Message(can_id, state['address'], bytes(state['payload']), state['timestamp'])


def build_read_request(address: int, block_type: str, identifier: int, mode: int = 0x01) -> bytes:
    """
    The D2 message to read an identifier, e.g. build_read_request(0x50, 'REID', 0x1A04) -> 50 A6 1A 04 01.
    mode 0x01 means 'send once'.
    """
    service, id_bytes, has_mode = READ_SERVICES[block_type]
    request = bytes([address, service]) + identifier.to_bytes(id_bytes, 'big')
    return request + bytes([mode]) if has_mode else request


# ---------------------------------------------------------------------------------------------------------------------
# Response decoding
# ---------------------------------------------------------------------------------------------------------------------

def get_bits(data: bytes, offset: int, length: int) -> Optional[int]:
    """
    Returns length bits starting at offset, where offset 0 is the most significant bit of the first byte, or None
    if data is too short. This came from Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.BinaryBuffer.GetBits.
    """
    if length <= 0 or offset + length > len(data) * 8:
        return None
    return (int.from_bytes(data, 'big') >> (len(data) * 8 - offset - length)) & ((1 << length) - 1)


def compare_number(compare_value: str) -> float:
    """
    The number of a compare value like '0x1A', '0b0101' or '12.5'. VIDA only accepts a lower case '0b' prefix and
    throws on the few compare values like '0B00000000' in the database; these are accepted here.
    Raises ValueError for compare values that are not numbers.
    """
    prefix = compare_value[:2].lower()
    if prefix == '0x':
        return float(int(compare_value[2:], 16))
    if prefix == '0b':
        return float(int(compare_value[2:], 2))
    return float(compare_value)


def compare(compare_value: str, value: float, operator: int) -> bool:
    """
    Whether a scaled value matches a compare value with the given T150_BlockValue operator. An empty compare value
    matches everything. This came from Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Comparer.Compare.
    """
    if compare_value == '':
        return True
    reference = compare_number(compare_value)
    if operator == 2:
        return value >= reference
    if operator == 3:
        return value <= reference
    if operator == 4:
        return value > reference
    if operator == 5:
        return value < reference
    return value == reference


def _format(hex_value: str, data_type: int) -> str:
    """
    Formats ASCII (51) and BCD+ASCII (53) data. Hex and BCD stay as hex digits. This came from
    Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Formatter.Format.
    """
    if data_type == 51:
        data = bytes.fromhex(hex_value).rstrip(b'\0')
        return ''.join(chr(b) if b >= 32 else f'[ascii{b:02x}]' for b in data)
    if data_type == 53 and len(hex_value) >= 7:
        return hex_value[:-6] + _format(hex_value[-6:], 51)
    return hex_value


@dataclass
class DecodedValue:
    name: str
    text: str
    value: object      # the scaled number, or the formatted string for hex/ASCII/BCD data
    unit: str
    raw: str           # the raw bits as hex
    matched: bool
    value_text: str = ''  # the text of the matching compare value, if any

    def __str__(self) -> str:
        if self.value_text:
            return f'{self.text}: {self.value_text} (raw 0x{self.raw})'
        value = f'{self.value:g}' if isinstance(self.value, float) else str(self.value)
        unit = f' {self.unit}' if self.unit else ''
        return f'{self.text}: {value}{unit} (raw 0x{self.raw})'


def to_signed(raw: int, bit_length: int) -> int:
    """
    Interprets raw as a two's complement number of bit_length bits.
    """
    return raw - (1 << bit_length) if bit_length > 0 and raw & (1 << (bit_length - 1)) else raw


@lru_cache(maxsize=None)
def _parse_scaling(expression: str):
    return parse_conversion(expression)


def match_block(raw: int, block) -> DecodedValue:
    """
    Returns the first block value (in sort order) whose compare value matches the scaled raw value. Works with
    carcom.Block and any object with the same attributes. This came from
    Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.ResponseHandler.MatchBlock.
    """
    hex_value = f'{raw:0{(block.length + 7) // 8 * 2}X}'
    for value in block.values:
        if block.data_type >= 50:
            if value.compare == '' or value.compare.lower() == '0x' + hex_value.lower():
                display = value.alternative or _format(hex_value, block.data_type)
                return DecodedValue(block.name, block.display_text, display, value.unit, hex_value, True,
                                    value.display_text)
            continue
        try:
            if block.data_type == 1:
                x = float(to_signed(raw, block.length))
            elif block.data_type == 3 and block.length == 32:
                x = struct.unpack('>f', raw.to_bytes(4, 'big'))[0]
            else:
                x = float(raw)
            scaled = evaluate_ast(_parse_scaling(value.scaling), x)
        except EXPRESSION_ERRORS:
            continue
        try:
            matched = compare(value.compare, scaled, value.operator)
        except ValueError:
            # VIDA catches the exception of an invalid compare value and shows no match at all.
            break
        if matched:
            return DecodedValue(block.name, block.display_text, value.alternative or scaled, value.unit, hex_value,
                                True, value.display_text if value.compare else '')
    return DecodedValue(block.name, block.display_text, hex_value, '', hex_value, False, 'No match')


@dataclass
class DecodedResponse:
    address: int
    service: int
    block_type: str = ''
    identifier: str = ''
    identifier_text: str = ''
    data: bytes = b''
    values: list[DecodedValue] = field(default_factory=list)
    error: str = ''

    def __str__(self) -> str:
        if self.error:
            return self.error
        lines = [f'{self.block_type} {self.identifier} "{self.identifier_text}" data={self.data.hex(" ").upper()}']
        return '\n'.join(lines + [f'    {value}' for value in self.values])


def decode_response(address: int, payload: bytes, ecu) -> DecodedResponse:
    """
    Decodes a D2 response payload (starting with the service byte) with the identifier definitions of the responding
    ECU. ecu needs get_block(block_type, identifier) and get_block_children(block_id, 'PARAM'), like carcom.EcuBlocks.
    This follows Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.ResponseHandler, which reads the parameters
    of an identifier with BinaryBuffer.GetBits and MatchBlock.
    """
    service = payload[0] if payload else -1
    response = DecodedResponse(address, service)
    if service == NEGATIVE_RESPONSE:
        requested = SERVICE_NAMES.get(payload[1], f'{payload[1]:02X}') if len(payload) > 1 else '?'
        code = f'{payload[2]:02X}' if len(payload) > 2 else '?'
        response.error = f'negative response to {requested}, code {code}'
    elif service == GENERAL_RESPONSE:
        response.error = 'general response (busy, request repeated)'
    elif service not in RESPONSE_TYPES:
        name = SERVICE_NAMES.get(service - 0x40, '')
        response.error = f'response {service:02X} {name}, data={payload[1:].hex(" ").upper()}'
    else:
        block_type = RESPONSE_TYPES[service]
        id_bytes = READ_SERVICES[block_type][1]
        response.block_type = block_type
        response.identifier = f'0x{int.from_bytes(payload[1:1 + id_bytes], "big"):0{id_bytes * 2}X}'
        response.data = payload[1 + id_bytes:]
        block = ecu.get_block(block_type, response.identifier)
        if block is None:
            response.error = f'{block_type} {response.identifier} (unknown), data={response.data.hex(" ").upper()}'
            return response
        response.identifier_text = block.display_text
        for param in ecu.get_block_children(block.id, 'PARAM'):
            raw = get_bits(response.data, param.offset, param.length)
            if raw is not None:
                response.values.append(match_block(raw, param))
    return response


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[2] not in READ_SERVICES:
        sys.exit(f'Usage: d2.py <ECU address in hex> <{"|".join(READ_SERVICES)}> <identifier in hex>\n'
                 'Prints the CAN frames to read an identifier, e.g. d2.py 50 REID 1A04')
    request = build_read_request(int(sys.argv[1], 16), sys.argv[2], int(sys.argv[3], 16))
    for frame in split_message(request):
        print(f'{REQUEST_CAN_ID:08X}#{frame.hex().upper()}')
