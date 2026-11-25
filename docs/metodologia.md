### Origem da ΔPD

Os cenários de curto prazo do NGFS (primeira safra, maio de 2025) combinam três modelos: **GEM-E3** (economia e setores), **EIRIN** (macrofinanceiro) e **CLIMACRED** (crédito). O CLIMACRED é um modelo estrutural de firma: o default ocorre quando o valor dos ativos fica abaixo das dívidas, e a mudança de expectativa do mercado sobre o cenário reprecifica ativos e fluxos de caixa. A saída é

ΔPD = PD(cenário) − PD(linha de base), em pontos percentuais, por setor, país e ano (2024–2030).

### Aplicação ao contrato

- **Soma direta:** PD_s = PD + ΔPD (uso previsto pelos autores do CLIMACRED para a firma representativa).
- **Deslocamento Δz:** Δz = Φ⁻¹(PD_ref + ΔPD) − Φ⁻¹(PD_ref) e PD_s = Φ(Φ⁻¹(PD) + Δz). Preserva a ordenação de risco; coincide com a soma direta quando PD = PD_ref.

Piso de PD de 0,030%. A PD de referência do setor é a média da carteira ponderada por EAD ou um valor único informado.

### Perdas e capital

- Perda esperada = PD × LGD × EAD.
- Capital econômico pela fórmula ASRF de Basileia (CRE31, corporativo, 99,9%, ajuste de prazo com M entre 1 e 5 anos).
- Excesso sobre provisão = Σ max(0, PE − provisão constituída).
- Impactos em % do Patrimônio de Referência informado. Balanço estático.

### Limites

A ΔPD ilustrativa usa cinco âncoras publicadas e premissas para os demais setores: substitua pela série do IIASA antes de qualquer uso. LGD constante; sem geografia intra-país; sem mitigadores como Proagro e seguro rural; horizonte da PD do CLIMACRED a confirmar na documentação técnica. Na abordagem padronizada o RWA regulatório não reage à PD; o capital ASRF é tratado como capital econômico.

### Referências

- NGFS (2025). *NGFS Short-Term Scenarios for central banks and supervisors* e documentação técnica. Dados: Battiston et al. (2025), NGFS Phase 5 Short Term Scenarios, Zenodo 10.5281/zenodo.15790097.
- Mandel, A., Battiston, S., Monasterolo, I. (2025). Mapping global financial risks under climate change. *Nature Climate Change*, 15, 329–334.
- Battiston, S., Mandel, A., Monasterolo, I., Roncoroni, A. (2023). Climate credit risk and corporate valuation. CEPR DP20239.
- Barón, A., Dassatti, C., Lavagna, G., Montañez-Enríquez, R. (2026). Assessing climate risks in Uruguay’s banks using NGFS short-term scenarios. *Latin American Journal of Central Banking*, 7, 100198.
- BCBS. CRE31 – IRB approach: risk weight functions. Resolução CMN 4.557/2017, com redação da Resolução CMN 4.943/2021.
