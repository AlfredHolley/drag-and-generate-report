"""
Parameter Descriptions for Medical Tests
Brief explanations of what each parameter represents
"""

PARAMETER_DESCRIPTIONS = {
    # Immune Status Parameters
    "T4 lymphocytes [T4]": "CD4+ T cells that coordinate immune responses and help activate other immune cells.",
    "T8 Lymphocytes [T8]": "CD8+ T cells that destroy virus-infected cells and tumor cells.",
    "TH1": "Type 1 helper T cells that promote cell-mediated immunity against intracellular pathogens.",
    "TH2": "Type 2 helper T cells that promote antibody-mediated immunity against extracellular pathogens.",
    "TH1 / TH2": "Ratio indicating balance between cell-mediated and humoral immune responses.",
    "TH17": "Helper T cells involved in inflammatory responses and defense against extracellular bacteria.",
    "Tregs": "Regulatory T cells that suppress immune responses and maintain immune homeostasis.",
    "TH17 / Tregs": "Ratio reflecting balance between pro-inflammatory and regulatory immune responses.",
    "TH9": "Helper T cells involved in allergic responses and defense against helminths.",
    "TH22": "Helper T cells that play a role in epithelial barrier immunity.",
    "Total Leukocytes [Leu]": "White blood cells that defend the body against infections and foreign substances.",
    "Total Lymphocytes [Lin]": "A type of white blood cell essential for adaptive immune responses.",
    "T lymphocytes [T]": "Lymphocytes that mature in the thymus and mediate cellular immunity.",
    "Ratio T4/T8 [T4/T8]": "Ratio of helper to cytotoxic T cells, indicating immune system balance.",
    "Activated T Lymphocytes [Tact]": "T cells currently engaged in immune responses.",
    "Activated T4 Lymphocytes [T4act]": "Active CD4+ T cells responding to antigens.",
    "Activated T8 Lymphocytes [T8act]": "Active CD8+ T cells engaged in killing infected cells.",
    "Lymphocytes T4 Helpers [T4H]": "Mature CD4+ T cells that provide help to other immune cells.",
    "Naïve T4 Lymphocytes [T4N]": "T4 cells that have not yet encountered their specific antigen.",
    "Ratio T4 helper/T4 naïve [T4h/T4n]": "Ratio indicating immune system experience and activation status.",
    "Regulatory T4 Lymphocytes [Treg]": "CD4+ T cells that suppress excessive immune responses.",
    "T4 Central Memory Lymphocytes [T4 CM]": "Long-lived T4 cells that can quickly respond to previously encountered antigens.",
    "T4 Effector Memory Lymphocytes [T4 EM]": "T4 cells that rapidly respond to antigens in peripheral tissues.",
    "Cytotoxic T8 Lymphocytes [T8 cyto]": "T8 cells specialized in killing infected or abnormal cells.",
    "Senescent T8 Lymphocytes [T8sen]": "Aged T8 cells with reduced functionality.",
    "Ratio T8 Cytotoxic / T8 Senescent [T8c/T8s]": "Ratio indicating functional capacity of cytotoxic T cells.",
    "T8 Central Memory Lymphocytes [T8 CM]": "Long-lived T8 cells providing long-term immunity.",
    "Memory Effector T8 Lymphocytes [T8 EM]": "T8 cells that provide rapid responses in peripheral tissues.",
    "NK lymphocytes [NK]": "Natural killer cells that provide innate immune defense against viruses and tumors.",
    "NKT lymphocytes [NKT]": "Cells with properties of both T cells and NK cells, involved in immune regulation.",
    "B lymphocytes [B]": "Lymphocytes that produce antibodies and mediate humoral immunity.",
    "- B1a lymphocytes [B1a]": "B cells that produce natural antibodies for early defense.",
    "Interleucine-2 Soluble Receptor [IL2r]": "Marker of T cell activation and immune system activity.",
    "Selective reactivity of the immune system": "Assessment of immune system responsiveness to stimulation.",
    "Neutrophils [Neu]": "Most abundant white blood cells that fight bacterial infections.",
    "Monocytes [Mono]": "White blood cells that differentiate into macrophages and dendritic cells.",
    "Classic monocytes [Mon C]": "The most abundant monocyte subset involved in phagocytosis.",
    "Intermediate Monocytes [Mon In]": "Monocytes with pro-inflammatory properties.",
    "Non-Classical Monocytes [Mon NC]": "Monocytes that patrol blood vessels and tissues.",
    "Eosinophils [Eos]": "White blood cells primarily involved in combating parasites and allergic reactions.",
    "Basophils [Bas]": "Least common white blood cells involved in allergic and inflammatory responses.",

    # Viral Antibodies
    "Herpes Simplex Type 1 IgG Ab [HSV1]": "Antibodies indicating past or current HSV-1 infection.",
    "Herpes Simplex Type 2 IgG Ab [HSV2]": "Antibodies indicating past or current HSV-2 infection.",
    "Citomegalovirus IgG Ab [CMV IgG]": "Antibodies showing previous exposure to cytomegalovirus.",
    "Epstein-Barr VCA IgM Ab [VCA IgM]": "Antibodies indicating recent or acute EBV infection.",
    "Epstein-Barr VCA IgG Ab [VCA IgG]": "Antibodies showing past EBV infection.",
    "Epstein-Barr Early IgG Ab [EA IgG]": "Antibodies associated with active or recent EBV infection.",
    "Epstein-Barr Nuclear EBNA IgG Ab [EBNA IgG]": "Antibodies indicating past EBV infection and immunity.",
    "Parvovirus B19 IgG Ab [PB19]": "Antibodies showing previous exposure to parvovirus B19.",
    "Varicella Zoster IgG Ab [VZV]": "Antibodies indicating immunity to varicella zoster virus (chickenpox).",

    # Hemogram Parameters
    "RBCs": "Red blood cells that transport oxygen throughout the body.",
    "Hemoglobin": "Protein in red blood cells that carries oxygen from lungs to tissues.",
    "Hematocrit": "Percentage of blood volume occupied by red blood cells.",
    "MCV": "Mean corpuscular volume - average size of red blood cells.",
    "MCH": "Mean corpuscular hemoglobin - average hemoglobin content per red blood cell.",
    "MCHC": "Mean corpuscular hemoglobin concentration - average hemoglobin concentration in red blood cells.",
    "RDW": "Red cell distribution width - variation in red blood cell size.",
    "Platelets": "Cell fragments essential for blood clotting.",
    "MPV": "Mean platelet volume - average size of platelets.",
    "Total Leukocyte": "Total count of white blood cells in the blood.",
    "Neutrophils": "White blood cells that fight bacterial infections.",
    "Lymphocytes": "White blood cells crucial for adaptive immune response.",
    "Monocytes": "White blood cells that develop into macrophages.",
    "Eosinophyles": "White blood cells involved in parasitic and allergic responses.",
    "Basophyles": "White blood cells involved in inflammatory responses.",

    # Intestinal Dysbiosis Parameters
    "Alpha-diversity (Shannon)": "Measure of microbial diversity in the gut, higher values indicate greater diversity.",
    "Firmicutes/Bacteroidetes-Ratio": "Ratio of two major bacterial phyla, imbalances may affect metabolism and health.",
    "pH": "Acidity or alkalinity of the gut environment, influences bacterial growth.",
    "Short-chain fatty acids, total": "Beneficial metabolites produced by gut bacteria from dietary fiber.",
    "Acetic acid": "Short-chain fatty acid involved in energy metabolism and gut health.",
    "Propionic acid": "Short-chain fatty acid with anti-inflammatory properties.",
    "Butyric acid": "Short-chain fatty acid that provides energy to colon cells and reduces inflammation.",
    "Actinobacteria": "Bacterial phylum including beneficial species like Bifidobacterium.",
    "Bacteroidetes (Bacteroidota)": "Major bacterial phylum involved in breaking down complex carbohydrates.",
    "Firmicutes (Bacillota)": "Major bacterial phylum including many beneficial species.",
    "Fusobacteriota": "Bacterial phylum, some species associated with inflammation.",
    "Proteobacteria (Pseudomonadota)": "Bacterial phylum, elevated levels may indicate dysbiosis.",
    "Verrucomicrobiota": "Bacterial phylum including Akkermansia, beneficial for gut barrier.",
    "Mucin Degradation [Deg Muc]": "Bacterial capacity to degrade protective mucus layer.",
    "Toxins": "Presence of bacterial toxins that may harm the gut.",
    "DNA": "Bacterial DNA balance indicator.",
    "Parasites": "Presence of parasitic organisms in the gut.",
    "Helminths": "Presence of parasitic worms.",
    "Archaea [ARCH]": "Single-celled organisms, some produce methane in the gut.",
    "SIBO": "Small intestinal bacterial overgrowth indicator.",
    "LIBO": "Large intestinal bacterial overgrowth indicator.",
    "IMO": "Intestinal methanogen overgrowth.",
    "ISO": "Intestinal sulfate-reducing organisms overgrowth.",
    "Digestion": "Overall assessment of digestive bacterial capacity.",
    "Vitamins": "Bacterial capacity to produce vitamins.",
    "Permeability": "Assessment of gut barrier integrity.",
    "Fungi and Yeasts [FUNG]": "Presence of fungal organisms in the gut.",
    "[LPS] or lipopolysaccharides": "Inflammatory molecules from gram-negative bacteria.",
    "Viruses [VIR]": "Presence of viral elements in the gut microbiome.",
    "TOTAL SCFA": "Total short-chain fatty acids, beneficial metabolites.",
    "SCFA Beneficial [SCFA Bene]": "Beneficial short-chain fatty acids supporting gut health.",
    "Parasites and Helminths [PAR]": "Combined assessment of parasitic organisms.",

    # Gut Barrier and Inflammation
    "Alpha-1-antitrypsin": "Protein marker of intestinal inflammation and protein loss.",
    "IgA": "Antibody that protects mucosal surfaces in the gut.",
    "Calprotectin": "Protein indicating intestinal inflammation.",
    "Zonulin": "Protein regulating gut permeability, elevated levels indicate leaky gut.",
    "Beta-defensin": "Antimicrobial peptide part of innate immune defense.",

    # Bacterial Species
    "Eubacterium spp.": "Beneficial bacteria producing short-chain fatty acids.",
    "Blautia spp.": "Beneficial bacteria with anti-inflammatory properties.",
    "Roseburia spp.": "Beneficial bacteria producing butyrate.",
    "Faecalibacterium spp.": "Highly beneficial bacteria, including F. prausnitzii.",
    "Bacteroides spp.": "Bacteria involved in breaking down complex carbohydrates.",
    "Prevotella spp.": "Bacteria associated with plant-rich diets.",
    "Lactobacillus": "Beneficial bacteria, probiotics, supporting gut health.",
    "Desulfovibrio spp.": "Bacteria producing hydrogen sulfide, may cause inflammation.",
    "Escherichia spp.": "Bacteria including E. coli, some strains beneficial, others pathogenic.",
    "Klebsiella spp.": "Bacteria, some strains opportunistic pathogens.",
    "Akkermansia muciniphila": "Beneficial bacteria strengthening gut barrier.",
    "Bifidobacterium spp.": "Highly beneficial probiotic bacteria.",
    "Streptococcus thermophilus": "Probiotic bacteria used in yogurt production.",
    "Collinsella aerofaciens": "Bacteria, elevated levels may indicate dysbiosis.",
    "Clostridium butyricum": "Beneficial bacteria producing butyrate.",
    "Clostridium perfringens": "Bacteria that can cause gastrointestinal infections.",
    "Clostridiodes difficile": "Bacteria causing antibiotic-associated diarrhea.",
    "Escherichia coli": "Common gut bacteria, most strains harmless, some pathogenic.",
    "Hafnia alvei": "Bacteria, generally harmless commensal.",
    "Klebsiella pneumoniae": "Opportunistic pathogen, can cause infections.",
    "Proteus mirabilis": "Bacteria associated with urinary tract infections.",
    "Yersinia enterocolitica": "Bacteria causing gastrointestinal infections.",
    "Pseudomonas putida": "Environmental bacteria, rarely pathogenic.",
    "Campylobacter jejuni": "Bacteria causing food poisoning.",
    "Fusobacterium nucleatum": "Bacteria associated with inflammation and colorectal cancer.",
    "Methanobrevibacter smithii": "Archaea producing methane gas.",
    "Methanosphaera stadtmanae": "Archaea producing methane.",
    "Methanomassiliicoccus luminyensis": "Archaea associated with methane production.",
    "Candida albicans": "Yeast that can cause infections when overgrown.",
    "Saccharomyces cerevisiae": "Yeast, generally beneficial, used in probiotics.",
    "Fusarium proliferatum": "Fungus, may produce mycotoxins.",
    "Debaryomyces hansenii": "Yeast found in fermented foods.",
}


def get_parameter_description(parameter_name):
    """
    Get a brief description for a parameter

    Args:
        parameter_name: Name of the parameter

    Returns:
        Description string or None if not found
    """
    return PARAMETER_DESCRIPTIONS.get(parameter_name, None)


def get_all_descriptions():
    """Get all parameter descriptions"""
    return PARAMETER_DESCRIPTIONS
