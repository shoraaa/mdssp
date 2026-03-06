import pandas as pd
from pathlib import Path

df = pd.read_csv('experiment_structural/structured/blocks/all_results.csv')
gcols = ['pattern', 'algorithm']
agg_dict = {
    'objective': ['mean', lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0],
}
agg = df.groupby(gcols, dropna=False).agg(agg_dict).reset_index()
print('Columns after groupby:', agg.columns.tolist())
