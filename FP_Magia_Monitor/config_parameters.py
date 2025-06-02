# 参数配置
PARAM_MAP = {
    'X': [(0, 2), (1, 0)],
    'Y': [(0, 3), (1, 1)],
    'Z': [(0, 4), (1, 2)],
    'Biso': [(0, 5), (1, 3)],
    'Occ': [(0, 6), (1, 4)],
    'beta11': [(2, 0), (3, 0)],
    'beta22': [(2, 1), (3, 1)],
    'beta33': [(2, 2), (3, 2)],
    'beta12': [(2, 3), (3, 3)],
    'beta13': [(2, 4), (3, 4)]
}

OPTIMIZED_RULES = {
    #General parameters
    " Scale ": [{"row_offset": 1, "col_offset": 0}, {"row_offset": 2, "col_offset": 0}],
    "Extinc": [{"row_offset": 1, "col_offset": 1}, {"row_offset": 2, "col_offset": 1}],
    " Bov ": [{"row_offset": 1, "col_offset": 2}, {"row_offset": 2, "col_offset": 2}],
    " Str1 ": [{"row_offset": 1, "col_offset": 3}, {"row_offset": 2, "col_offset": 3}],
    " Str2 ": [{"row_offset": 1, "col_offset": 4}, {"row_offset": 2, "col_offset": 4}],
    " Str3 ": [{"row_offset": 1, "col_offset": 5}, {"row_offset": 2, "col_offset": 5}],

    #Instrument parameters
    " Zero ": [{"row_offset": 1, "col_offset": 0}, {"row_offset": 1, "col_offset": 1}],
    " Dtt1 ": [{"row_offset": 1, "col_offset": 2}, {"row_offset": 1, "col_offset": 3}],
    " Dtt2 ": [{"row_offset": 1, "col_offset": 4}, {"row_offset": 1, "col_offset": 5}],
    " Dtt_1overd ": [{"row_offset": 1, "col_offset": 6}, {"row_offset": 1, "col_offset": 7}],


    #Peak parameters
    "Sigma-2": [{"row_offset": 2, "col_offset": 0}, {"row_offset": 3, "col_offset": 0}],
    "Sigma-1": [{"row_offset": 2, "col_offset": 1}, {"row_offset": 3, "col_offset": 1}],
    "Sigma-0": [{"row_offset": 2, "col_offset": 2}, {"row_offset": 3, "col_offset": 2}],
    "Sigma-Q": [{"row_offset": 2, "col_offset": 3}, {"row_offset": 3, "col_offset": 3}],
    "Iso-GStrain": [{"row_offset": 2, "col_offset": 4}, {"row_offset": 3, "col_offset": 4}],
    "Iso-GSize": [{"row_offset": 2, "col_offset": 5}, {"row_offset": 3, "col_offset": 5}],
    "Ani-LSize": [{"row_offset": 2, "col_offset": 6}, {"row_offset": 3, "col_offset": 6}],

    "Gamma-2": [{"row_offset": 2, "col_offset": 0}, {"row_offset": 3, "col_offset": 0}],
    "Gamma-1": [{"row_offset": 2, "col_offset": 1}, {"row_offset": 3, "col_offset": 1}],
    "Gamma-0": [{"row_offset": 2, "col_offset": 2}, {"row_offset": 3, "col_offset": 2}],
    "Iso-LorStrain": [{"row_offset": 2, "col_offset": 3}, {"row_offset": 3, "col_offset": 3}],
    "Iso-LorSize": [{"row_offset": 2, "col_offset": 4}, {"row_offset": 3, "col_offset": 4}],

    #Lattice parameters
    " a ": [{"row_offset": 1, "col_offset": 0}, {"row_offset": 2, "col_offset": 0}],
    " b ": [{"row_offset": 1, "col_offset": 1}, {"row_offset": 2, "col_offset": 1}],
    " c ": [{"row_offset": 1, "col_offset": 2}, {"row_offset": 2, "col_offset": 2}],
    " alpha ": [{"row_offset": 1, "col_offset": 3}, {"row_offset": 2, "col_offset": 3}],
    " beta ": [{"row_offset": 1, "col_offset": 4}, {"row_offset": 2, "col_offset": 4}],
    " gamma ": [{"row_offset": 1, "col_offset": 5}, {"row_offset": 2, "col_offset": 5}],

    #Preference parameters
    " Pref1 ": [{"row_offset": 2, "col_offset": 0}, {"row_offset": 3, "col_offset": 0}],
    " Pref2 ": [{"row_offset": 2, "col_offset": 1}, {"row_offset": 3, "col_offset": 1}],
    " alph0 ": [{"row_offset": 2, "col_offset": 2}, {"row_offset": 3, "col_offset": 2}],
    " beta0 ": [{"row_offset": 2, "col_offset": 3}, {"row_offset": 3, "col_offset": 3}],
    " alph1 ": [{"row_offset": 2, "col_offset": 4}, {"row_offset": 3, "col_offset": 4}],
    " beta1 ": [{"row_offset": 2, "col_offset": 5}, {"row_offset": 3, "col_offset": 5}],
    " alphQ ": [{"row_offset": 2, "col_offset": 6}, {"row_offset": 3, "col_offset": 6}],
    " betaQ ": [{"row_offset": 2, "col_offset": 7}, {"row_offset": 3, "col_offset": 7}],

    #Absorption correction parameters
    "ABSCOR1": [{"row_offset": 0, "col_offset": 0}, {"row_offset": 0, "col_offset": 1}],
    "ABSCOR2": [{"row_offset": 0, "col_offset": 2}, {"row_offset": 0, "col_offset": 3}]

}