"""Configuração: anos, cenários NGFS de curto prazo, setores GEM-E3, de-para CNAE e âncoras."""
from __future__ import annotations

import re

YEARS = [2025, 2026, 2027, 2028, 2029, 2030]

PD_FLOOR = 0.0003  # piso de PD (Basileia, CRE32)
PD_CAP = 0.9999
ASRF_CONF = 0.999

# Cenários de curto prazo do NGFS (primeira safra, maio de 2025)
SCENARIOS = [
    {"id": "H2P", "curto": "H2P", "nome": "Highway to Paris", "tipo": "Transição ordenada"},
    {"id": "SWUC", "curto": "SWUC", "nome": "Sudden Wake-Up Call", "tipo": "Transição abrupta"},
    {"id": "DIRE", "curto": "DIRE", "nome": "Diverging Realities", "tipo": "Físico no Brasil (seco 2026, úmido 2029)"},
    {"id": "DAPS_AS", "curto": "DAPS Am. Sul", "nome": "Disasters and Policy Stagnation – América do Sul", "tipo": "Físico (seco 2026, úmido 2027)"},
    {"id": "DAPS_ASIA", "curto": "DAPS Ásia", "nome": "Disasters and Policy Stagnation – Ásia", "tipo": "Contágio via comércio"},
]

# Setores GEM-E3 agregados: (código, nome em português, nome GEM-E3)
SECTORS = [
    ("agri", "Agricultura", "Agriculture"),
    ("forest", "Silvicultura e biomassa", "Biomass solid / forestry"),
    ("coal", "Carvão", "Coal"),
    ("crude", "Petróleo bruto", "Crude oil"),
    ("gas", "Gás natural", "Gas"),
    ("oil", "Derivados de petróleo", "Oil"),
    ("power", "Energia elétrica", "Power supply"),
    ("ferrous", "Metais ferrosos", "Ferrous metals"),
    ("nonferrous", "Metais não ferrosos", "Non-ferrous metals"),
    ("chem", "Química", "Chemical products"),
    ("eint", "Outras ind. intensivas em energia", "Other energy intensive"),
    ("elec", "Bens elétricos", "Electric goods"),
    ("transeq", "Equipamentos de transporte", "Transport equipment"),
    ("otheq", "Outros bens de capital", "Other equipment goods"),
    ("cons", "Bens de consumo e alimentos", "Consumer goods industries"),
    ("constr", "Construção", "Construction"),
    ("landtr", "Transporte terrestre", "Land transport"),
    ("airtr", "Transporte aéreo", "Air transport"),
    ("watertr", "Transporte aquaviário", "Water transport"),
    ("mserv", "Serviços de mercado", "Market services"),
    ("nmserv", "Serviços não mercantis", "Non-market services"),
]
SECTOR_NAME = {s[0]: s[1] for s in SECTORS}

# Valores da ΔPD ilustrativa que vêm de fontes publicadas (os demais são premissas)
ANCHORS = {
    ("DIRE", "agri", 2026): "Barón et al. (2026), América do Sul: 23,30 p.p.",
    ("DAPS_AS", "agri", 2026): "Barón et al. (2026), América do Sul: 25,77 p.p.",
    ("SWUC", "coal", 2030): "NGFS (2025), mundo: +35 p.p. no carvão",
    ("SWUC", "crude", 2030): "NGFS (2025), mundo: +12 p.p. no petróleo",
    ("DAPS_AS", "power", 2027): "NGFS (2025): mais de 10 p.p. em energia elétrica",
}

# De-para CNAE 2.0 (divisão) -> setor GEM-E3
MAP_ROWS = [
    ("01, 03", "agri"), ("02, 16", "forest"), ("05", "coal"), ("06", "crude"),
    ("07, 24", "ferrous"), ("08, 09, 17, 18, 23", "eint"), ("10–15, 31–33", "cons"),
    ("19", "oil"), ("20–22", "chem"), ("25, 28", "otheq"), ("26, 27", "elec"),
    ("29, 30", "transeq"), ("35", "power"), ("41–43", "constr"), ("49", "landtr"),
    ("50", "watertr"), ("51", "airtr"), ("84–88", "nmserv"),
    ("36–39, 45–47, 52–83, 90–99", "mserv"),
]


def cnae_to_sector(div) -> str | None:
    try:
        d = int(str(div).strip()[:2])
    except (TypeError, ValueError):
        return None
    if d in (1, 3):
        return "agri"
    if d in (2, 16):
        return "forest"
    if d == 5:
        return "coal"
    if d == 6:
        return "crude"
    if d in (7, 24):
        return "ferrous"
    if d in (8, 9, 17, 18, 23):
        return "eint"
    if 10 <= d <= 15 or 31 <= d <= 33:
        return "cons"
    if d == 19:
        return "oil"
    if 20 <= d <= 22:
        return "chem"
    if d in (25, 28):
        return "otheq"
    if d in (26, 27):
        return "elec"
    if d in (29, 30):
        return "transeq"
    if d == 35:
        return "power"
    if 41 <= d <= 43:
        return "constr"
    if d == 49:
        return "landtr"
    if d == 50:
        return "watertr"
    if d == 51:
        return "airtr"
    if 84 <= d <= 88:
        return "nmserv"
    if d >= 36:
        return "mserv"
    return None


# Reconhecimento do setor pelo nome da variável do IIASA (ordem importa)
_KEYS = [
    (r"coal fired|gas fired|oil fired|\bpv\b|wind|hydro|nuclear|power|electricity", "power"),
    (r"non.?ferrous", "nonferrous"), (r"ferrous", "ferrous"), (r"coal", "coal"),
    (r"crude", "crude"), (r"biomass|forest", "forest"), (r"agri", "agri"),
    (r"chemical", "chem"), (r"energy.?intensive", "eint"), (r"electric", "elec"),
    (r"transport equip", "transeq"), (r"equipment", "otheq"), (r"consumer", "cons"),
    (r"construction", "constr"), (r"land transport", "landtr"), (r"air transport", "airtr"),
    (r"water transport", "watertr"), (r"non.?market", "nmserv"), (r"market services", "mserv"),
    (r"\bgas\b", "gas"), (r"\boil\b", "oil"),
]


def sector_id(name) -> str | None:
    if name is None:
        return None
    t = str(name).strip()
    if not t or t.lower() == "nan":
        return None
    if t in SECTOR_NAME:
        return t
    for pat, sid in _KEYS:
        if re.search(pat, t, flags=re.I):
            return sid
    return None


COUNTRY_ALIASES = {
    "brazil": "Brasil", "united states": "Estados Unidos", "usa": "Estados Unidos",
    "chile": "Chile", "argentina": "Argentina", "mexico": "México", "south america": "América do Sul",
}

INPUT_LAYOUT = [
    ("id_contrato", "texto", "Identificador único", "C0001"),
    ("cliente", "texto", "Nome ou código do tomador", "Agropecuária Alfa S.A."),
    ("cnae", "texto", "Divisão CNAE 2.0 (2 dígitos)", "01"),
    ("setor_ngfs", "texto, opcional", "Setor GEM-E3 (código ou nome em inglês); prevalece sobre o CNAE", "agri"),
    ("pais", "texto", "País de risco", "Brasil"),
    ("uf", "texto, opcional", "UF da atividade (reservado para choque geográfico)", "MT"),
    ("rating", "texto, opcional", "Rating interno", "BB"),
    ("pd_12m", "decimal", "PD de 12 meses", "0.012"),
    ("lgd", "decimal", "LGD", "0.45"),
    ("ead", "número", "Exposição no default (R$ mi)", "85.4"),
    ("prazo_anos", "número", "Prazo efetivo M (anos)", "3"),
    ("provisao", "número, opcional", "Provisão constituída (R$ mi)", "0.52"),
]
