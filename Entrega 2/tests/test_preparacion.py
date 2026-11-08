"""Pruebas mínimas reproducibles sin depender de datos privados/reales."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from src.entrega2 import parse_mixed_dates, prepare_sessions, build_daily_panel, features_from_panel

class TestDatos(unittest.TestCase):
    def test_formato_fechas(self):
        parsed = parse_mixed_dates(pd.Series(['1/1/2018 17:49','2023-06-02 05:23:17']))
        self.assertEqual(parsed.dt.year.tolist(), [2018,2023])

    def test_dedup_y_ceros_solo_entre_sesiones(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'mini.csv'
            pd.DataFrame({
                'Station_Name':['BOULDER / A','BOULDER / A','BOULDER / A','BOULDER / A'],
                'Address':['X']*4,
                'Start_Date___Time':['1/1/2023 07:00','2023-01-01 07:00:00','1/3/2023 07:00','1/4/2023 07:00'],
                'Energy__kWh_':[2,2,4,0],
                'Total_Duration__hh_mm_ss_':['01:00:00']*4,
            }).to_csv(f,index=False)
            sessions,summary=prepare_sessions(f)
            self.assertEqual(len(sessions),2)
            self.assertEqual(summary['duplicados_detectados_con_regla_conservadora'],1)
            panel,_=build_daily_panel(sessions)
            self.assertEqual(panel['sesiones'].tolist(),[1,0,1])
            self.assertEqual(panel['sin_registro'].tolist(),[False,True,False])
            self.assertEqual(len(features_from_panel(panel)),0)

if __name__ == '__main__':
    unittest.main()
