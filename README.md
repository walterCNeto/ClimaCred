# ClimaCred

Teste de estresse climático para carteiras de crédito PJ usando a **ΔPD por setor do modelo CLIMACRED**, publicada nos cenários de curto prazo do NGFS (2025–2030). O app lê uma carteira, aplica a ΔPD de cada cenário ao contrato e gera o impacto em **perda esperada** e **capital econômico (ASRF)**, em R$ e em % do Patrimônio de Referência.

> A ΔPD que acompanha o repositório (`data/dpd_ilustrativa.csv`) é **ilustrativa**: cinco valores vêm de fontes publicadas e os demais são premissas. Para resultados de uso real, carregue a série oficial do NGFS Scenario Explorer (IIASA).

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Testes: `pip install pytest` e `python -m pytest -q`.

## Estrutura

```
app.py                     interface Streamlit
climacred/config.py        cenários, setores GEM-E3, de-para CNAE, âncoras
climacred/engine.py        aplicação da ΔPD (soma direta ou Δz), perda esperada, capital ASRF
climacred/io.py            leitura da carteira e da ΔPD (formato largo do IIASA ou longo)
climacred/report.py        tabelas, relatório em texto e exportação para Excel
data/carteira_exemplo.csv  carteira fictícia (160 contratos)
data/dpd_ilustrativa.csv   ΔPD ilustrativa, 5 cenários × 21 setores × 2025–2030
docs/metodologia.md        metodologia e referências (exibida no app)
docs/climacred_web.html    versão em página única (HTML) do mesmo cálculo
tests/test_engine.py       testes do motor e dos leitores
```

## Entradas

**Carteira (CSV)** — separador vírgula ou ponto e vírgula; decimal com ponto ou vírgula.

| coluna | descrição |
|---|---|
| id_contrato, cliente | identificação |
| cnae | divisão CNAE 2.0 (2 dígitos), convertida para setor GEM-E3 |
| setor_ngfs | opcional; código do app (`agri`, `power`…) ou nome GEM-E3 em inglês; prevalece sobre o CNAE |
| pais, uf | país de risco; UF reservada para choque geográfico |
| rating | opcional |
| pd_12m, lgd | em decimal (0.012 = 1,2%) |
| ead, provisao | R$ mi |
| prazo_anos | prazo efetivo M |

**ΔPD (CSV)** — formato largo exportado do NGFS Scenario Explorer (`Model, Scenario, Region, Variable, Unit, 2024…2030`; o setor é o último trecho de `Variable`, filtrado por "default") ou formato longo `cenario, pais, setor, ano, delta_pd_pp`.

Para obter a série: NGFS Scenario Explorer da IIASA → base *NGFS Phase 5 Short-Term* (entrada como convidado) → região *Brazil* → variáveis de probabilidade de default por setor → exportar CSV.

## Metodologia (resumo)

- **Soma direta:** PD_s = PD + ΔPD.
- **Deslocamento Δz:** Δz = Φ⁻¹(PD_ref + ΔPD) − Φ⁻¹(PD_ref); PD_s = Φ(Φ⁻¹(PD) + Δz). Preserva a ordenação de risco e coincide com a soma direta quando PD = PD_ref.
- **Perda esperada** = PD × LGD × EAD. **Capital** pela fórmula ASRF (CRE31, 99,9%, ajuste de prazo). Balanço estático.

Detalhes, limites e referências em `docs/metodologia.md`.

## Referências principais

- NGFS (2025). *NGFS Short-Term Scenarios for central banks and supervisors* e documentação técnica; dados em Battiston et al. (2025), Zenodo 10.5281/zenodo.15790097.
- Mandel, Battiston, Monasterolo (2025). *Nature Climate Change*, 15, 329–334.
- Battiston, Mandel, Monasterolo, Roncoroni (2023). CEPR DP20239.
- Barón, Dassatti, Lavagna, Montañez-Enríquez (2026). *Latin American Journal of Central Banking*, 7, 100198.

Licença: MIT.
