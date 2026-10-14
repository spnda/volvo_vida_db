#!/usr/bin/env python3
"""
Query library for the VIDA carcom database (the T1xx tables).

The central concept of carcom is the block tree of an ECU variant (T100_EcuVariant):

    T144_BlockChild links blocks (T141_Block) into a tree per ECU variant. The root is block 1 (ROOT).
    Directly below ROOT are, among others, the diagnostic identifiers of an ECU:
        REID   - 'Record identifier', read with D2 service A6 (Read Current Data By Identifier, 2 byte identifier)
        REOFF  - 'Record offset', read with A5 (Read Current Data By Offset, 1 byte offset)
        BLOFF  - 'Block offset', read with B9 (Read Data Block By Offset), written with B8
        RTOFF  - 'Routine offset', started with B2 (Control Routine By Offset)
        ADDR   - memory address, read with A7 (Read Current Data By Address)
        DTC    - diagnostic trouble codes, each with freeze frame records (COMP -> REID) below them
    Each identifier block has a T150_BlockValue whose CompareValue is the identifier itself (e.g. '0x1A04').
    Below an identifier are PARAM blocks. offset and length of a PARAM are in *bits*, counted from the most
    significant bit of the first data byte after the identifier in the response (see d2.get_bits).
    Every PARAM has one or more T150_BlockValue rows. A row either has an empty CompareValue (the parameter is a
    continuous value, converted with the T155_Scaling expression) or a CompareValue + Operator pair which maps the
    *scaled* value to a text (enumerations, states, ...). VIDA picks the first matching row in SortOrder.

As and Ppe texts:

    Every block and block value has two sets of texts. VIDA calls them As and Ppe (the BlockHandler.Mode enum in
    Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Blocks) but never spells the names out. Judging by the
    data, As are the translated texts a workshop technician sees, and Ppe the names engineers gave the signals:

        T141_Block       As: fkT190_Text, translated, e.g. '30-supply'
                         Ppe: name, untranslated, e.g. 'VBat_A_Sense'
        T150_BlockValue  As: fkT190_Text_Value, fkT190_Text_Unit, fkT155_Scaling, e.g. unit 'Volt'
                         Ppe: fkT190_Text_ppeValue, fkT190_Text_ppeUnit, fkT155_ppeScaling, e.g. unit 'V'

    The scalings of the two sets usually agree, but not always: for engine speed (identifier 0x1165 of the ECM
    30684976 A) the As set has 'x*1' with the unit 'inches Hg', the Ppe set 'x/4' with the unit 'rpm'.

    BlockHandler.Mode defaults to As. In As mode, a block shows its As text if there is one, otherwise its Ppe
    name, and a block value uses its As set if it has a scaling (fkT155_Scaling > 0), otherwise its Ppe set.
    Ppe mode, which VehicleServiceDatabase.CloneForPpe switches to, always shows the Ppe names and uses the Ppe set
    unless it has no scaling. Which parts of VIDA use Ppe mode is not visible in the available assemblies.
    This came from BlockHandler.addBlocks and Block.DisplayText in
    Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Blocks. addBlocks reads the result of the
    service__GetBlocks stored procedure by column number; which T150_BlockValue column each number is, is inferred
    from the column names, as the stored procedure is not part of the CSV export.

This module is a port of Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Blocks.BlockHandler on top of
duckdb, plus a number of helper queries for ECUs, configurations, services, DTCs and texts.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Iterable, Optional

import duckdb
import pandas as pd

from read_csv import get_csvs, DatabaseFile, root_directory
from vin_decoder import decode_vin, Vehicle

DEFAULT_LANGUAGE = 'en-US'

# Block types of the identifiers an ECU can be asked for (see the module docstring)
IDENTIFIER_TYPES = ('REID', 'REOFF', 'BLOFF', 'ADDR', 'RTOFF')

COMPARE_OPERATORS = {0: '', 1: '==', 2: '>=', 3: '<=', 4: '>', 5: '<'}
DATA_TYPES = {1: 'signed', 2: 'unsigned', 3: 'float', 50: 'hex', 51: 'ascii', 52: 'bcd', 53: 'bcd_ascii'}


def _sql(query: str, params: Optional[list] = None) -> pd.DataFrame:
    if params is None:
        return duckdb.sql(query).df()
    return duckdb.execute(query, params).df()


def _int(value, default: int = 0) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return default
    return int(value)


def _str(value) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value)


# ---------------------------------------------------------------------------------------------------------------------
# Texts
# ---------------------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=None)
def get_language_id(language: str = DEFAULT_LANGUAGE) -> int:
    """
    Returns the T193_Language id for a language code like 'en-US' or 'de-DE'.
    VIDA maps en-GB and sv-SE to en-US for block texts (BlockHandler.GetText).
    """
    get_csvs(DatabaseFile.t193)
    if language in ('en-GB', 'sv-SE'):
        language = 'en-US'
    df = _sql('SELECT id FROM t193 WHERE identifier = ?', [language])
    if df.empty:
        raise ValueError(f'Unknown language {language}')
    return int(df['id'].iloc[0])


def get_texts(text_ids: Iterable[int], language: str = DEFAULT_LANGUAGE) -> dict[int, str]:
    """
    Resolves a set of T190_Text ids to their texts in one query.
    """
    ids = sorted({int(i) for i in text_ids if i})
    if not ids:
        return {}
    get_csvs(DatabaseFile.t191)
    ids_df = pd.DataFrame({'id': ids})
    df = duckdb.sql(f"""
        SELECT t.fkT190_Text AS id, t.data FROM t191 t
        INNER JOIN ids_df ON ids_df.id = t.fkT190_Text
        WHERE t.fkT193_Language = {get_language_id(language)}
    """).df()
    return {int(row.id): _str(row.data) for row in df.itertuples()}


def search_texts(pattern: str, language: str = DEFAULT_LANGUAGE, limit: int = 100) -> pd.DataFrame:
    """
    Case-insensitive search through all texts of a language. Returns the text ID, category and text.
    """
    get_csvs(DatabaseFile.t190, DatabaseFile.t191, DatabaseFile.t192)
    return _sql(f"""
        SELECT td.fkT190_Text AS text_id, tc.identifier AS category, td.data AS text
        FROM t191 td
        LEFT JOIN t190 t ON t.id = td.fkT190_Text
        LEFT JOIN t192 tc ON tc.id = t.fkT192_TextCategory
        WHERE td.fkT193_Language = ? AND td.data ILIKE ?
        ORDER BY td.fkT190_Text
        LIMIT {int(limit)}
    """, [get_language_id(language), f'%{pattern}%'])


# ---------------------------------------------------------------------------------------------------------------------
# Profiles, ECUs and communication configuration
# ---------------------------------------------------------------------------------------------------------------------

def get_vehicle_ecus(profile_identifiers: Iterable[str], language: str = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """
    Returns the default ECU variants (T160_DefaultEcuVariant) for all given vehicle profiles, joined with the
    communication configuration (T121_Config), bus (T123_Bus) and protocol (T122_Protocol).
    These are the ECUs VIDA assumes to be in the car before it reads the actual part numbers from the vehicle.
    bus_type is the T123_Bus identifier, which matches Vcc.Vida.DiagSwdl.VehCom2.BusType: 1 is high speed CAN,
    0 is low speed CAN, 3 is K-line.
    """
    get_csvs(DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102, DatabaseFile.t120, DatabaseFile.t121,
             DatabaseFile.t122, DatabaseFile.t123, DatabaseFile.t124, DatabaseFile.t160, DatabaseFile.t161,
             DatabaseFile.t191)
    ids = pd.DataFrame({'identifier': list(profile_identifiers)})
    return duckdb.sql(f"""
        SELECT DISTINCT
            ev.id AS ecu_variant_id, ev.identifier AS ecu_variant, e.id AS ecu_id, e.identifier AS ecu,
            e.name AS ecu_name, et.identifier AS ecu_type, et.description AS ecu_type_name,
            coalesce(td.data, et.description) AS ecu_type_text,
            c.id AS config_id, c.fkT123_Bus AS bus_id, bus.name AS bus, bus.identifier AS bus_type,
            net.identifier AS net,
            pr.identifier AS protocol, c.physicalAddress AS physical_address, c.functionalAddress AS functional_address,
            c.canAddress AS can_address, c.commAddress AS comm_address, c.priority, c.canIdTX AS can_id_tx,
            c.canIdRX AS can_id_rx, c.canIdFunc AS can_id_func, c.canIdUUDT AS can_id_uudt, c.busRate AS bus_rate,
            c.addressSize AS address_size, c.fkT121_Config_Gateway AS gateway_config_id,
            c.fkT130_Init_Diag AS init_diag_id, c.fkT130_Init_Timing AS init_timing_id,
            first(p.title) OVER (PARTITION BY ev.id ORDER BY p.folderLevel DESC) AS profile_title
        FROM ids
        INNER JOIN t161 p ON p.identifier = ids.identifier
        INNER JOIN t160 d ON d.fkT161_Profile = p.id
        INNER JOIN t100 ev ON ev.id = d.fkT100_EcuVariant
        INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
        INNER JOIN t102 et ON et.id = e.fkT102_EcuType
        LEFT JOIN t191 td ON td.fkT190_Text = et.fkt190_Text AND td.fkT193_Language = {get_language_id(language)}
        LEFT JOIN t120 ce ON ce.fkT100_EcuVariant = ev.id
        LEFT JOIN t121 c ON c.id = ce.fkT121_Config
        LEFT JOIN t123 bus ON bus.id = c.fkT123_Bus
        LEFT JOIN t124 net ON net.id = bus.fkT124_Net
        LEFT JOIN t122 pr ON pr.id = c.fkT122_Protocol
        ORDER BY c.fkT123_Bus, c.physicalAddress, ev.identifier
    """).df()


def get_ecu_variant(identifier_or_id: str | int) -> pd.DataFrame:
    """
    Returns the T100_EcuVariant row together with ECU and ECU type for an ECU variant identifier
    (like '30728979 AA') or a numeric T100 id.
    """
    get_csvs(DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102)
    if isinstance(identifier_or_id, int) or str(identifier_or_id).isdigit():
        where, param = 'ev.id = ?', int(identifier_or_id)
    else:
        where, param = 'ev.identifier = ?', str(identifier_or_id)
    return _sql(f"""
        SELECT ev.id AS ecu_variant_id, ev.identifier AS ecu_variant, ev.status, e.id AS ecu_id, e.identifier AS ecu,
               e.name AS ecu_name, et.id AS ecu_type_id, et.identifier AS ecu_type, et.description AS ecu_type_name,
               ev.fkT101_Ecu_Gateway AS gateway_ecu_id
        FROM t100 ev
        INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
        INNER JOIN t102 et ON et.id = e.fkT102_EcuType
        WHERE {where}
    """, [param])


def get_ecu_variants_of_type(ecu_type: str) -> pd.DataFrame:
    """
    Returns all ECU variants (all hardware/software part numbers VIDA knows) for an ECU type identifier like
    '284101' (ECM NI4) or '372302' (CEM). Useful to pick the variant that is really fitted to a car.
    """
    get_csvs(DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102)
    return _sql("""
        SELECT ev.id AS ecu_variant_id, ev.identifier AS ecu_variant, ev.status, e.identifier AS ecu, e.name AS ecu_name
        FROM t100 ev
        INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
        INNER JOIN t102 et ON et.id = e.fkT102_EcuType
        WHERE et.identifier = ?
        ORDER BY ev.identifier
    """, [str(ecu_type)])


def get_ecu_types(language: str = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """
    Returns all ECU types VIDA knows (T102_EcuType) with their name.
    """
    get_csvs(DatabaseFile.t102, DatabaseFile.t191)
    return _sql(f"""
        SELECT et.identifier AS ecu_type, et.description, td.data AS text
        FROM t102 et
        LEFT JOIN t191 td ON td.fkT190_Text = et.fkt190_Text AND td.fkT193_Language = {get_language_id(language)}
        WHERE et.identifier != '0' AND len(et.identifier) = 6
        ORDER BY et.identifier
    """)


def get_ecu_addresses(language: str = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """
    Returns every communication address used by any ECU in VIDA, with the ECU type at that address.
    """
    get_csvs(DatabaseFile.t100, DatabaseFile.t101, DatabaseFile.t102, DatabaseFile.t120, DatabaseFile.t121,
             DatabaseFile.t191)
    return _sql(f"""
        SELECT DISTINCT c.commAddress AS address, et.identifier AS ecu_type, td.data AS text
        FROM t121 c
        INNER JOIN t120 ce ON ce.fkT121_Config = c.id
        INNER JOIN t100 ev ON ev.id = ce.fkT100_EcuVariant
        INNER JOIN t101 e ON e.id = ev.fkT101_Ecu
        INNER JOIN t102 et ON et.id = e.fkT102_EcuType
        LEFT JOIN t191 td ON td.fkT190_Text = et.fkt190_Text AND td.fkT193_Language = {get_language_id(language)}
        ORDER BY address, ecu_type
    """)


def get_ecu_config_values(init_id: int) -> pd.DataFrame:
    """
    Returns the initialisation/timing values (T131_InitValue) of a T130_Init entry, as referenced by
    T121_Config.fkT130_Init_Diag and fkT130_Init_Timing (retries, keep-alive period, P2/P3 timings, ...).
    """
    get_csvs(DatabaseFile.t130, DatabaseFile.t131, DatabaseFile.t132, DatabaseFile.t133)
    return _sql("""
        SELECT i.id AS init_id, ic.name AS category, iv.sortOrder AS sort_order, ivt.name, iv.initValue AS value
        FROM t130 i
        INNER JOIN t133 ic ON ic.id = i.fkT133_InitCategory
        INNER JOIN t131 iv ON iv.fkT130_Init = i.id
        INNER JOIN t132 ivt ON ivt.id = iv.fkT132_InitValueType
        WHERE i.id = ?
        ORDER BY iv.sortOrder
    """, [int(init_id)])


def get_hw_settings(profile_identifiers: Iterable[str]) -> dict[str, str]:
    """
    Returns the communication tool settings of a vehicle: T136_InitHw_Profile links profiles to T130_Init entries
    with values like Baud_can_hs_1 (high speed CAN), Baud_can_ls (low speed CAN), Mecu_address (the gateway ECU) and
    Ctl_the_relay. If multiple profiles define settings, the most specific (highest folder level) wins.
    This came from Vcc.Vida.DiagSwdl.BizServices.CarCom.DB.CarComRepository.GetInitHwSettings and
    Vcc.Vida.DiagSwdl.BizServices.CarCom.DB.EcuData.HwSettings.
    """
    get_csvs(DatabaseFile.t131, DatabaseFile.t132, DatabaseFile.t136, DatabaseFile.t161)
    ids = pd.DataFrame({'identifier': list(profile_identifiers)})
    df = duckdb.sql("""
        SELECT p.folderLevel, t.name, v.initValue AS value
        FROM ids INNER JOIN t161 p ON p.identifier = ids.identifier
        INNER JOIN t136 h ON h.fkT161_Profile = p.id
        INNER JOIN t131 v ON v.fkT130_Init = h.fkT130_Init
        INNER JOIN t132 t ON t.id = v.fkT132_InitValueType
        ORDER BY p.folderLevel, v.sortOrder
    """).df()
    return {row.name: _str(row.value) for row in df.itertuples()}


def get_ecu_services(ecu_variant_id: int) -> pd.DataFrame:
    """
    Returns all diagnostic services (T111_Service) that an ECU variant supports according to T110.
    The service definition XML (T111_Service.definition) is not part of the CSV; sql/extract_services.ps1 writes
    it to extracted_services/<service_id>.xml.
    """
    get_csvs(DatabaseFile.t110, DatabaseFile.t111, DatabaseFile.t122)
    return _sql("""
        SELECT s.id AS service_id, p.identifier AS protocol, s.service, s.mode, s.serviceName AS service_name,
               s.modeName AS mode_name, s.description, s.type
        FROM t110 se
        INNER JOIN t111 s ON s.id = se.fkT111_Service
        LEFT JOIN t122 p ON p.id = s.fkT122_Protocol
        WHERE se.fkT100_EcuVariant = ?
        ORDER BY s.service, s.mode
    """, [int(ecu_variant_id)])


# ---------------------------------------------------------------------------------------------------------------------
# Block tree (port of BlockHandler)
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class BlockValue:
    compare: str
    operator: int
    scaling: str
    alternative: str
    value_text: str = ''
    unit_text: str = ''
    # The texts of the other (As/Ppe) column set, used as fallback for display purposes.
    fallback_value_text: str = ''
    fallback_unit_text: str = ''
    fallback_scaling: str = ''

    @property
    def operator_symbol(self) -> str:
        return COMPARE_OPERATORS.get(self.operator, '==')

    @property
    def display_text(self) -> str:
        return self.alternative or self.value_text or self.fallback_value_text

    @property
    def unit(self) -> str:
        return self.unit_text or self.fallback_unit_text


@dataclass
class Block:
    id: int
    block_type: str
    data_type: int
    name: str
    text_id: int
    offset: int
    length: int
    exclude: bool
    composite: bool
    text: str = ''
    values: list[BlockValue] = field(default_factory=list)

    @property
    def display_text(self) -> str:
        """
        The As text if there is one, otherwise the Ppe name. text is only set in As mode.
        """
        return self.text or self.name

    @property
    def data_type_name(self) -> str:
        return DATA_TYPES.get(self.data_type, str(self.data_type))

    @property
    def identifier(self) -> str:
        """
        For identifier blocks (REID, BLOFF, ...) and DTCs, the CompareValue of the first block value.
        """
        for value in self.values:
            if value.compare:
                return value.compare
        return ''

    @property
    def unit(self) -> str:
        for value in self.values:
            if value.unit:
                return value.unit
        return ''


@dataclass
class BlockChild:
    child: int
    parent: int
    order: int


class EcuBlocks:
    """
    The complete block tree of one ECU variant, loaded with a handful of queries. The methods mirror the ones from
    VIDA's BlockHandler, so their behaviour (e.g. offset handling for composite blocks) is the same.
    """

    def __init__(self, ecu_variant_id: int, language: str = DEFAULT_LANGUAGE, mode: str = 'as'):
        """
        mode is 'as' or 'ppe', see 'As and Ppe texts' in the module docstring.
        """
        self.ecu_variant_id = int(ecu_variant_id)
        self.language = language
        self.mode = mode
        self.blocks: dict[int, Block] = {}
        self.children: list[BlockChild] = []
        self._children_by_parent: dict[int, list[BlockChild]] = {}
        self._load()

    def _load(self):
        get_csvs(DatabaseFile.t141, DatabaseFile.t142, DatabaseFile.t144, DatabaseFile.t150, DatabaseFile.t155)
        structure = _sql("""
            SELECT fkT141_Block_Child AS child, fkT141_Block_Parent AS parent, SortOrder AS sort_order
            FROM t144 WHERE fkT100_EcuVariant = ?
        """, [self.ecu_variant_id])
        self.children = [BlockChild(int(r.child), int(r.parent), _int(r.sort_order))
                         for r in structure.itertuples()]
        for child in self.children:
            self._children_by_parent.setdefault(child.parent, []).append(child)

        blocks = _sql("""
            WITH ids AS (SELECT DISTINCT fkT141_Block_Child AS id FROM t144 WHERE fkT100_EcuVariant = ?
                         UNION SELECT DISTINCT fkT141_Block_Parent FROM t144 WHERE fkT100_EcuVariant = ?)
            SELECT b.id, bt.identifier AS block_type, b.fkT143_BlockDataType AS data_type, b.name, b.fkT190_Text AS text_id,
                   b.offset, b.length, b.exclude, b.composite
            FROM ids INNER JOIN t141 b ON b.id = ids.id
            INNER JOIN t142 bt ON bt.id = b.fkT142_BlockType
        """, [self.ecu_variant_id, self.ecu_variant_id])
        for r in blocks.itertuples():
            self.blocks[int(r.id)] = Block(int(r.id), r.block_type, _int(r.data_type), _str(r.name), _int(r.text_id),
                                           _int(r.offset), _int(r.length), bool(r.exclude), bool(r.composite))

        values = _sql("""
            WITH ids AS (SELECT DISTINCT fkT141_Block_Child AS id FROM t144 WHERE fkT100_EcuVariant = ?)
            SELECT v.fkT141_Block AS block, v.CompareValue AS compare,
                   v.Operator AS operator, v.fkT190_Text_Value AS as_value, v.fkT190_Text_Unit AS as_unit,
                   v.fkT155_Scaling AS as_scaling_id, s.definition AS as_scaling, v.altDisplayValue AS alt,
                   v.fkT190_Text_ppeValue AS ppe_value, v.fkT190_Text_ppeUnit AS ppe_unit,
                   v.fkT155_ppeScaling AS ppe_scaling_id, ps.definition AS ppe_scaling
            FROM ids INNER JOIN t150 v ON v.fkT141_Block = ids.id
            LEFT JOIN t155 s ON s.id = v.fkT155_Scaling
            LEFT JOIN t155 ps ON ps.id = v.fkT155_ppeScaling
            ORDER BY v.fkT141_Block, v.SortOrder, v.Id
        """, [self.ecu_variant_id])

        text_ids = {b.text_id for b in self.blocks.values()}
        for column in ('as_value', 'as_unit', 'ppe_value', 'ppe_unit'):
            text_ids.update(int(v) for v in values[column].dropna())
        texts = get_texts(text_ids, self.language)
        if self.mode == 'as':
            for block in self.blocks.values():
                block.text = texts.get(block.text_id, '')

        for r in values.itertuples():
            block = self.blocks.get(int(r.block))
            if block is None:
                continue
            compare, operator = _str(r.compare), _int(r.operator)
            if block.block_type == 'PARAM' and block.data_type >= 50:
                # Hex/ASCII/BCD parameters are never scaled.
                block.values.append(BlockValue(compare, operator, 'x', ''))
                continue
            as_set = (_int(r.as_value), _int(r.as_unit), _str(r.as_scaling) or 'x*1')
            ppe_set = (_int(r.ppe_value), _int(r.ppe_unit), _str(r.ppe_scaling) or 'x*1')
            use_as = (self.mode == 'as' and _int(r.as_scaling_id) > 0) or \
                     (self.mode == 'ppe' and _int(r.ppe_scaling_id) == 0)
            (value_text, unit_text, scaling), other = (as_set, ppe_set) if use_as else (ppe_set, as_set)
            block.values.append(BlockValue(compare, operator, scaling, _str(r.alt), texts.get(value_text, ''),
                                           texts.get(unit_text, ''), texts.get(other[0], ''),
                                           texts.get(other[1], ''), other[2]))

    # -- BlockHandler API ------------------------------------------------------------------------------------------

    def get_blocks(self, block_type: str) -> list[Block]:
        """
        All blocks of a type anywhere in the tree (BlockHandler.GetBlocks).
        """
        result = []
        for child in self.children:
            block = self.blocks.get(child.child)
            if block is not None and block.block_type == block_type:
                result.append(block)
        return result

    def get_block(self, block_type: str, identifier: str) -> Optional[Block]:
        """
        Finds the block of a type whose value matches the identifier, e.g. get_block('REID', '0x1A04').
        """
        for child in self.children:
            block = self.blocks.get(child.child)
            if block is None or block.block_type != block_type:
                continue
            if any(identifier == value.compare for value in block.values):
                return block
        return None

    def get_block_children(self, parent_block_id: int, block_type: str, offset: int = 0) -> list[Block]:
        """
        Port of BlockHandler.getBlockChildren: returns the children of a type, descending into composite blocks and
        accumulating their offsets.
        """
        parent = self.blocks.get(parent_block_id)
        children = sorted(self._children_by_parent.get(parent_block_id, []), key=lambda c: c.order)
        result: list[Block] = []
        running_offset = 0
        for child in children:
            block = self.blocks.get(child.child)
            if block is None:
                continue
            if block.block_type == block_type:
                if not block.exclude:
                    result.append(replace(block, offset=block.offset + offset) if offset > 0 else block)
            elif block.composite:
                if not block.exclude:
                    result.extend(self.get_block_children(block.id, block_type, offset + block.offset))
            elif parent is not None and parent.composite:
                if not block.exclude:
                    result.extend(self.get_block_children(block.id, block_type, block.offset + running_offset))
                running_offset += block.length
        return result

    # -- Convenience -----------------------------------------------------------------------------------------------

    def get_identifiers(self, block_types: Iterable[str] = IDENTIFIER_TYPES) -> list[Block]:
        """
        Returns the identifier blocks of the given types directly below ROOT. This leaves out the identifiers inside
        DTC freeze frame records.
        """
        block_types = set(block_types)
        found = {c.child: self.blocks[c.child] for c in self._children_by_parent.get(1, []) if c.child in self.blocks}
        result = [b for b in found.values() if b.block_type in block_types and not b.exclude]
        return sorted(result, key=lambda b: (b.block_type, _identifier_sort_key(b.identifier)))

    def get_dtcs(self) -> list[Block]:
        return sorted({b.id: b for b in self.get_blocks('DTC')}.values(), key=lambda b: _identifier_sort_key(b.identifier))

    def get_freeze_frame_identifiers(self, dtc_block_id: int) -> list[Block]:
        """
        The identifiers recorded in the freeze frame of a DTC (DTC -> AC10_E1 -> Records -> REID).
        """
        return self.get_block_children(dtc_block_id, 'REID')


def _identifier_sort_key(identifier: str):
    try:
        return (0, int(identifier, 16) if identifier.lower().startswith('0x') else int(identifier))
    except ValueError:
        return (1, identifier)


@lru_cache(maxsize=64)
def load_ecu_blocks(ecu_variant_id: int, language: str = DEFAULT_LANGUAGE, mode: str = 'as') -> EcuBlocks:
    return EcuBlocks(ecu_variant_id, language, mode)


# ---------------------------------------------------------------------------------------------------------------------
# Tabular exports
# ---------------------------------------------------------------------------------------------------------------------

def get_parameter_table(ecu_variant_id: int, language: str = DEFAULT_LANGUAGE,
                        block_types: Iterable[str] = IDENTIFIER_TYPES) -> pd.DataFrame:
    """
    Returns one row per identifier parameter of an ECU variant: identifier type and value, parameter name,
    bit offset/length, data type, scaling, unit and the enumeration texts.
    """
    ecu = load_ecu_blocks(int(ecu_variant_id), language)
    rows = []
    for identifier in ecu.get_identifiers(block_types):
        params = ecu.get_block_children(identifier.id, 'PARAM')
        for param in params:
            continuous = [v for v in param.values if v.compare == '']
            states = [f'{v.operator_symbol}{v.compare}: {v.display_text}' for v in param.values if v.compare != '']
            rows.append({
                'identifier_type': identifier.block_type,
                'identifier': identifier.identifier,
                'identifier_name': identifier.display_text,
                'identifier_length': identifier.length,
                'parameter_id': param.id,
                'parameter_name': param.name,
                'parameter_text': param.display_text,
                'offset': param.offset,
                'length': param.length,
                'data_type': param.data_type_name,
                'scaling': continuous[0].scaling if continuous else (param.values[0].scaling if param.values else ''),
                'unit': param.unit,
                'states': '; '.join(states),
            })
        if not params:
            rows.append({
                'identifier_type': identifier.block_type, 'identifier': identifier.identifier,
                'identifier_name': identifier.display_text, 'identifier_length': identifier.length,
            })
    return pd.DataFrame(rows)


def get_dtc_table(ecu_variant_id: int, language: str = DEFAULT_LANGUAGE) -> pd.DataFrame:
    """
    Returns the DTCs of an ECU variant with their description texts.
    """
    ecu = load_ecu_blocks(int(ecu_variant_id), language)
    rows = []
    for dtc in ecu.get_dtcs():
        value = dtc.values[0] if dtc.values else None
        rows.append({
            'dtc': dtc.identifier,
            'name': dtc.name,
            'text': dtc.display_text,
            'description': value.display_text if value else '',
            'freeze_frame_identifiers': ' '.join(b.identifier for b in ecu.get_freeze_frame_identifiers(dtc.id)),
        })
    return pd.DataFrame(rows)


def export_vehicle(vehicle: Vehicle, folder: str, language: str = DEFAULT_LANGUAGE):
    """
    Writes the ECUs of a vehicle to <folder>/<vin>/ecus.csv and the identifier parameters of each ECU to
    <folder>/<vin>/<ECU>_<variant>.csv.
    """
    folder = os.path.join(folder, vehicle.vin)
    os.makedirs(folder, exist_ok=True)

    profile_identifiers = vehicle.get_vehicle_profiles()
    ecus = get_vehicle_ecus(profile_identifiers, language)
    ecus.to_csv(os.path.join(folder, 'ecus.csv'), index=False, encoding='utf-8')
    for row in ecus.drop_duplicates('ecu_variant_id').itertuples():
        path = os.path.join(folder, f'{row.ecu}_{row.ecu_variant}.csv')
        print(f'Writing {path}')
        get_parameter_table(row.ecu_variant_id, language).to_csv(path, index=False, encoding='utf-8')


if __name__ == '__main__':
    import argparse

    # --language and --csv are accepted by every command
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--language', default=DEFAULT_LANGUAGE)
    common.add_argument('--csv', help='Write the result to a CSV file instead of printing it')
    parser = argparse.ArgumentParser(description='Query the VIDA carcom database.')
    sub = parser.add_subparsers(dest='command', required=True)
    for command, argument, help_text in [
        ('ecus', 'vin', 'List the default ECU variants of a vehicle'),
        ('params', 'ecu_variant', "List all identifier parameters of an ECU variant ('30728979 AA' or a T100 id)"),
        ('dtcs', 'ecu_variant', 'List the DTCs of an ECU variant'),
        ('services', 'ecu_variant', 'List the diagnostic services of an ECU variant'),
        ('variants', 'ecu_type', "List all variants of an ECU type (like '372302')"),
        ('text', 'pattern', 'Search all texts'),
        ('types', None, 'List all ECU types'),
        ('addresses', None, 'List all ECU addresses'),
    ]:
        command_parser = sub.add_parser(command, help=help_text, parents=[common])
        if argument:
            command_parser.add_argument(argument)
    export = sub.add_parser('export', help='Write the ECUs of a vehicle and the parameters of each ECU to CSV files')
    export.add_argument('vin')
    export.add_argument('folder', nargs='?', help='Output folder (default: <root>/ecu)')
    export.add_argument('--language', default=DEFAULT_LANGUAGE)
    args = parser.parse_args()

    def variant_id(value: str) -> int:
        df = get_ecu_variant(value)
        if df.empty:
            raise SystemExit(f'Unknown ECU variant {value}')
        return int(df['ecu_variant_id'].iloc[0])

    if args.command == 'export':
        export_vehicle(decode_vin(args.vin), args.folder or os.path.join(root_directory, 'ecu'),
                       args.language)
        sys.exit()
    if args.command == 'ecus':
        result = get_vehicle_ecus(decode_vin(args.vin).get_vehicle_profiles(), args.language)
    elif args.command == 'params':
        result = get_parameter_table(variant_id(args.ecu_variant), args.language)
    elif args.command == 'dtcs':
        result = get_dtc_table(variant_id(args.ecu_variant), args.language)
    elif args.command == 'services':
        result = get_ecu_services(variant_id(args.ecu_variant))
    elif args.command == 'variants':
        result = get_ecu_variants_of_type(args.ecu_type)
    elif args.command == 'types':
        result = get_ecu_types(args.language)
    elif args.command == 'addresses':
        result = get_ecu_addresses(args.language)
    else:
        result = search_texts(args.pattern, args.language)

    if args.csv:
        result.to_csv(args.csv, index=False, encoding='utf-8')
    else:
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 250,
                               'display.max_colwidth', 80):
            sys.stdout.reconfigure(encoding='utf-8')
            print(result.to_string(index=False))
