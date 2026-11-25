### Origem da ΔPD

Os cenários de curto prazo do NGFS (primeira safra, maio de 2025) combinam três modelos: **GEM-E3** (economia e setores), **EIRIN** (macrofinanceiro) e **CLIMACRED** (crédito). O CLIMACRED é um modelo estrutural de firma: o default ocorre quando o valor dos ativos fica abaixo das dívidas, e a mudança de expectativa do mercado sobre o cenário reprecifica ativos e fluxos de caixa. A saída é

ΔPD = PD(cenário) − PD(baseline), em pontos percentuais, por setor, país e ano (2024–2030).

No arquivo do IIASA (`CLIMACRED_IIASA_2025_07_02.xlsx`, versão 1.1) as variáveis são `pd_adjustment|<setor>` (ΔPD, "abs. change in value with respect to BAU in percentage points") e `baseline_pd|<setor>` (PD baseline, "value/level in percentage points"), para 50 setores e 53 regiões. O Brasil (`Brazil - BRA`) tem série própria em quatro cenários: HWTP (Highway to Paris), SWUC (Sudden Wake-Up Call), DIRE (Diverging Realities) e DAPS_SAM (Disasters and Policy Stagnation com eventos na América do Sul). As demais versões do DAPS não trazem o Brasil.

A PD baseline do CLIMACRED para o Brasil é a mesma em todos os setores e fica entre 35% e 45% ao longo de 2024–2030. Esse nível é muito superior a uma PD de 12 meses de carteira corporativa, o que indica uma escala própria do modelo estrutural; por isso a soma direta da ΔPD a PDs de 12 meses mistura escalas.

### Aplicação ao contrato

- **Soma direta:** PD_s = PD + ΔPD (uso previsto pelos autores do CLIMACRED para a firma representativa).
- **Deslocamento Δz:** Δz = Φ⁻¹(PD_ref + ΔPD) − Φ⁻¹(PD_ref) e PD_s = Φ(Φ⁻¹(PD) + Δz). Preserva a ordenação de risco; coincide com a soma direta quando PD = PD_ref.

PD de referência do Δz (premissa a escolher): (i) `baseline_pd` do CLIMACRED, que mede o choque na escala do próprio modelo e é a opção padrão; (ii) média da carteira no setor, ponderada por EAD; (iii) valor único informado. Piso de PD de 0,030%.

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

### CreditRisk+ (capital econômico de carteira)

Modelo atuarial (Credit Suisse First Boston, 1997): inadimplências Poisson com intensidade PD·(w₀ + Σ w_k X_k), fatores setoriais X_k ~ Gama com média 1. A distribuição de perdas, em múltiplos da unidade L₀ = max(LGD·EAD)/nº de bandas, sai da função geradora de probabilidades, avaliada por FFT (equivalente à recursão de Panjer).

**CEA = PE + PI**, com PE = Σ PD·LGD·EAD e PI = Q_q(L) − E[L]. No estresse, as mesmas exposições com as PDs estressadas: **CEA_stress = PE_stress + PI_stress**.

Calibragem parametrizável na barra lateral: nível de confiança; volatilidade relativa σ/μ da taxa de inadimplência de cada fator; peso idiossincrático w₀; estrutura de fatores (um por setor CLIMACRED ou fator único); multiplicador de σ/μ no estresse; nº de bandas.
