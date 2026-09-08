import unittest, tempfile, sqlite3
from pathlib import Path
from core.material_engine import hard_filter, score_materials

class CoreTests(unittest.TestCase):
    def setUp(self): self.rules=Path(__file__).parents[1]/'rules/weights.json'; self.ms=[{'name':'A','tensile_strength_mpa':600,'elastic_modulus_gpa':200,'temperature_max_c':300},{'name':'B','tensile_strength_mpa':None,'elastic_modulus_gpa':70,'temperature_max_c':500}]
    def test_temperature_filter(self):
        kept,rej=hard_filter(self.ms,{'temperature':400}); self.assertEqual(len(kept),1); self.assertEqual(rej[0]['material']['name'],'A')
    def test_missing_not_zero(self):
        ranked,_=score_materials(self.ms,{'part_type':'轴','weights':{'strength':5}},self.rules); b=next(x for x in ranked if x['material']['name']=='B'); self.assertIn('strength',b['missing'])
    def test_top_three(self):
        ranked,_=score_materials(self.ms,{'part_type':'支架'},self.rules); self.assertEqual(len(ranked),2)
    def test_missing_data_has_completeness(self):
        ranked,_=score_materials(self.ms,{'part_type':'轴','weights':{'strength':5,'stiffness':1}},self.rules)
        self.assertTrue(0 < ranked[0]['completeness'] < 100)
        self.assertTrue(all(x['score'] > 0 for x in ranked))
    def test_numeric_scores_rank_by_important_properties(self):
        materials = [
            {"name":"A","tensile_strength_mpa":1000,"elastic_modulus_gpa":300,"temperature_max_c":500,"raw_text":"成本高"},
            {"name":"B","tensile_strength_mpa":600,"elastic_modulus_gpa":200,"temperature_max_c":400,"raw_text":"成本中等"},
            {"name":"C","tensile_strength_mpa":300,"elastic_modulus_gpa":100,"temperature_max_c":300,"raw_text":"成本低"},
        ]
        ranked,_ = score_materials(materials, {"part_type":"其他","weights":{"strength":5,"stiffness":5,"cost":1}}, self.rules)
        self.assertEqual([item["material"]["name"] for item in ranked], ["A","B","C"])
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])
        self.assertGreater(ranked[1]["score"], ranked[2]["score"])
    def test_text_evidence_is_not_default_excellent_score(self):
        materials = [{"name":"text-only","raw_text":"该材料耐磨性较好。"}]
        ranked,_ = score_materials(materials, {"part_type":"其他","weights":{"wear":5}}, self.rules)
        self.assertIn("wear", ranked[0]["missing"])
        self.assertEqual(ranked[0]["score"], 0.0)

if __name__=='__main__': unittest.main()
