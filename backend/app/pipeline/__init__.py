from . import s1_ingest, s2_extract, s3_validate, s4_vendor, s5_duplicate, s6_po_match, s7_numeric, s8_decide, s9_output

STAGES = [(1, s1_ingest), (2, s2_extract), (3, s3_validate), (4, s4_vendor), (5, s5_duplicate),
          (6, s6_po_match), (7, s7_numeric), (8, s8_decide), (9, s9_output)]
