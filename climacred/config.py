"""Configuração: anos, cenários NGFS de curto prazo, setores GEM-E3/CLIMACRED, de-para CNAE."""
from __future__ import annotations

import re

YEARS = [2024, 2025, 2026, 2027, 2028, 2029, 2030]

PD_FLOOR = 0.0003  # piso de PD (Basileia, CRE32)
PD_CAP = 0.9999
ASRF_CONF = 0.999

# Cenários de curto prazo do NGFS com série para o Brasil (CLIMACRED v1.1, jul/2025)
SCENARIOS = [
    {"id": "HWTP", "curto": "H2P", "nome": "Highway to Paris", "tipo": "Transição ordenada"},
    {"id": "SWUC", "curto": "SWUC", "nome": "Sudden Wake-Up Call", "tipo": "Transição abrupta"},
    {"id": "DIRE", "curto": "DIRE", "nome": "Diverging Realities", "tipo": "Físico no Brasil (seco 2026, úmido 2029)"},
    {"id": "DAPS_SAM", "curto": "DAPS Am. Sul", "nome": "Disasters and Policy Stagnation – América do Sul",
     "tipo": "Físico (seco 2026, úmido 2027)"},
]
_OTHER_DAPS = [
    {"id": f"DAPS_{k}", "curto": f"DAPS {v[0]}", "nome": f"Disasters and Policy Stagnation – {v[1]}", "tipo": "Físico (outra região)"}
    for k, v in {"NAM": ("Am. N.", "América do Norte"), "EUR": ("Europa", "Europa"), "ASIA": ("Ásia", "Ásia"),
                 "OCE": ("Oceania", "Oceania"), "AFR_R": ("África", "África")}.items()]
SCEN_BY_ID = {s["id"]: s for s in SCENARIOS + _OTHER_DAPS}

# Setores do CLIMACRED (nomes exatos da base do IIASA) e nome em português
SECTORS = {
    "Agriculture": "Agricultura", "Biomass Solid": "Silvicultura e biomassa sólida", "Biofuels": "Biocombustíveis",
    "Biomass": "Geração a biomassa", "Coal": "Carvão", "Crude Oil": "Petróleo bruto", "Gas": "Gás natural",
    "Oil": "Derivados de petróleo", "Power Supply": "Energia elétrica (distribuição e mix)",
    "Hydro electric": "Geração hidrelétrica", "Wind": "Geração eólica", "PV": "Geração solar",
    "Gas Fired": "Geração a gás", "Coal fired": "Geração a carvão", "Oil Fired": "Geração a óleo",
    "Nuclear": "Geração nuclear", "Geothermal": "Geração geotérmica", "Hydrogen": "Hidrogênio",
    "Clean Gas": "Gás limpo", "CCS coal": "Carvão com CCS", "CSS Gas": "Gás com CCS", "CSS Bio": "Bioenergia com CCS",
    "CO2 Capture": "Captura de CO₂", "Ferrous metals": "Metais ferrosos", "Non-ferrous metals": "Metais não ferrosos",
    "Non-metallic minerals": "Minerais não metálicos (cimento, vidro, cerâmica)", "Chemical Products": "Química",
    "Basic pharmaceutical products": "Farmacêutica", "Rubber and plastic products": "Borracha e plástico",
    "Paper products, publishing": "Papel, celulose e editorial", "Fabricated Metal products": "Produtos de metal",
    "Computer, electronic and optical products": "Eletrônicos e ópticos", "Other Equipment Goods": "Máquinas e equipamentos",
    "Advanced Electric Appliances": "Eletrodomésticos avançados",
    "Advanced Heating and Cooking Appliances": "Aquecimento e cocção avançados", "Batteries": "Baterias",
    "Equipment for PV panels": "Equipamentos solares", "Equipment for wind power technology": "Equipamentos eólicos",
    "Equipment for CCS power technology": "Equipamentos de CCS",
    "Transport equipment (excluding EV)": "Veículos e equipamentos de transporte", "EV Transport Equipment": "Veículos elétricos",
    "Consumer Goods Industries": "Bens de consumo e alimentos", "Construction": "Construção",
    "Land transport": "Transporte terrestre", "Air transport": "Transporte aéreo", "Water transport": "Transporte aquaviário",
    "Warehousing": "Armazenagem e logística", "Market Services": "Serviços de mercado (comércio, finanças, imobiliário etc.)",
    "Non Market Services": "Serviços não mercantis (adm. pública, educação, saúde)", "R&D": "Pesquisa e desenvolvimento",
}
SECTOR_NAME = SECTORS

# Valores publicados que a ΔPD ilustrativa (demonstração) usa como âncora
ANCHORS = {
    ("DIRE", "Agriculture", 2026): "Barón et al. (2026), América do Sul: 23,30 p.p.",
    ("DAPS_SAM", "Agriculture", 2026): "Barón et al. (2026), América do Sul: 25,77 p.p.",
    ("SWUC", "Coal", 2030): "NGFS (2025), mundo: +35 p.p. no carvão",
    ("SWUC", "Crude Oil", 2030): "NGFS (2025), mundo: +12 p.p. no petróleo",
    ("DAPS_SAM", "Power Supply", 2027): "NGFS (2025): mais de 10 p.p. em energia elétrica",
}

# De-para CNAE 2.0 -> setor CLIMACRED (divisão de 2 dígitos; classes de 4 dígitos têm precedência)
CLASS_MAP = {  # prefixos de 4 dígitos
    "1931": "Biofuels", "1932": "Biofuels", "0721": "Non-ferrous metals", "0722": "Non-ferrous metals",
    "0723": "Non-ferrous metals", "0724": "Non-ferrous metals", "0725": "Non-ferrous metals", "0729": "Non-ferrous metals",
    "2441": "Non-ferrous metals", "2442": "Non-ferrous metals", "2443": "Non-ferrous metals", "2449": "Non-ferrous metals",
    "0600": "Crude Oil", "3520": "Gas", "2910": "Transport equipment (excluding EV)",
}
DIV_MAP = {}
for divs, sec in [
    ((1, 3), "Agriculture"), ((2, 16), "Biomass Solid"), ((5,), "Coal"), ((6,), "Crude Oil"), ((7, 24), "Ferrous metals"),
    ((8, 9, 23), "Non-metallic minerals"), (tuple(range(10, 16)) + (31, 32, 33), "Consumer Goods Industries"),
    ((17, 18), "Paper products, publishing"), ((19,), "Oil"), ((20,), "Chemical Products"),
    ((21,), "Basic pharmaceutical products"), ((22,), "Rubber and plastic products"), ((25,), "Fabricated Metal products"),
    ((26,), "Computer, electronic and optical products"), ((27, 28), "Other Equipment Goods"),
    ((29, 30), "Transport equipment (excluding EV)"), ((35,), "Power Supply"), ((41, 42, 43), "Construction"),
    ((49,), "Land transport"), ((50,), "Water transport"), ((51,), "Air transport"), ((52,), "Warehousing"),
    ((72,), "R&D"), ((84, 85, 86, 87, 88), "Non Market Services"),
]:
    for d in divs:
        DIV_MAP[d] = sec

MAP_ROWS = [
    ("01, 03", "Agriculture"), ("02, 16", "Biomass Solid"), ("05", "Coal"), ("06", "Crude Oil"),
    ("07, 24 (0721–0729 e 2441–2449: não ferrosos)", "Ferrous metals"), ("08, 09, 23", "Non-metallic minerals"),
    ("10–15, 31–33", "Consumer Goods Industries"), ("17, 18", "Paper products, publishing"),
    ("19 (1931–1932: biocombustíveis)", "Oil"), ("20", "Chemical Products"), ("21", "Basic pharmaceutical products"),
    ("22", "Rubber and plastic products"), ("25", "Fabricated Metal products"),
    ("26", "Computer, electronic and optical products"), ("27, 28", "Other Equipment Goods"),
    ("29, 30", "Transport equipment (excluding EV)"), ("35 (3520: gás)", "Power Supply"), ("41–43", "Construction"),
    ("49", "Land transport"), ("50", "Water transport"), ("51", "Air transport"), ("52", "Warehousing"), ("72", "R&D"),
    ("84–88", "Non Market Services"), ("36–39, 45–48, 53–71, 73–83, 90–99", "Market Services"),
]


def cnae_to_sector(code) -> str | None:
    s = re.sub(r"\D", "", str(code or ""))
    if len(s) >= 4 and s[:4] in CLASS_MAP:
        return CLASS_MAP[s[:4]]
    if len(s) < 2:
        return None
    d = int(s[:2])
    if d in DIV_MAP:
        return DIV_MAP[d]
    if d >= 36:
        return "Market Services"
    return None


# Códigos curtos da versão anterior do app (compatibilidade da coluna setor_ngfs)
LEGACY = {
    "agri": "Agriculture", "forest": "Biomass Solid", "coal": "Coal", "crude": "Crude Oil", "gas": "Gas", "oil": "Oil",
    "power": "Power Supply", "ferrous": "Ferrous metals", "nonferrous": "Non-ferrous metals", "chem": "Chemical Products",
    "eint": "Non-metallic minerals", "elec": "Computer, electronic and optical products",
    "transeq": "Transport equipment (excluding EV)", "otheq": "Other Equipment Goods", "cons": "Consumer Goods Industries",
    "constr": "Construction", "landtr": "Land transport", "airtr": "Air transport", "watertr": "Water transport",
    "mserv": "Market Services", "nmserv": "Non Market Services",
}
_LOWER = {k.lower(): k for k in SECTORS}


def sector_id(name) -> str | None:
    """Normaliza o nome do setor para o nome exato do CLIMACRED."""
    if name is None:
        return None
    t = str(name).strip()
    if not t or t.lower() == "nan":
        return None
    if t in SECTORS:
        return t
    return LEGACY.get(t.lower()) or _LOWER.get(t.lower())


def normalize_country(region: str) -> str:
    """'Brazil - BRA' -> 'Brasil'; 'South America' -> 'América do Sul'."""
    r = re.sub(r"\s*-\s*[A-Z]{3}$", "", str(region)).strip()
    return COUNTRY_ALIASES.get(r.lower(), r)


COUNTRY_ALIASES = {
    "brazil": "Brasil", "united states": "Estados Unidos", "usa": "Estados Unidos", "argentina": "Argentina",
    "mexico": "México", "south america": "América do Sul", "north america": "América do Norte", "world": "Mundo",
}

INPUT_LAYOUT = [
    ("id_contrato", "texto", "Identificador único", "C0001"),
    ("cliente", "texto", "Nome ou código do tomador", "Agropecuária Alfa S.A."),
    ("cnae", "texto", "CNAE 2.0: divisão (2 dígitos) ou classe (4+ dígitos)", "0115"),
    ("setor_ngfs", "texto, opcional", "Setor CLIMACRED em inglês; prevalece sobre o CNAE", "Hydro electric"),
    ("pais", "texto", "País de risco", "Brasil"),
    ("uf", "texto, opcional", "UF da atividade (reservado para choque geográfico)", "MT"),
    ("rating", "texto, opcional", "Rating interno", "BB"),
    ("pd_12m", "decimal", "PD de 12 meses", "0.012"),
    ("lgd", "decimal", "LGD", "0.45"),
    ("ead", "número", "Exposição no default (R$ mi)", "85.4"),
    ("prazo_anos", "número", "Prazo efetivo M (anos)", "3"),
    ("provisao", "número, opcional", "Provisão constituída (R$ mi)", "0.52"),
    ("estagio", "inteiro, opcional", "Estágio (Res. CMN 4.966): 1, 2 ou 3; estágio 3 não recebe choque de PD", "1"),
]
