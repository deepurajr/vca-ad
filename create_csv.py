import pandas as pd

# df1 = pd.read_csv('VCA2_Original_ADHC_10_22_2022.csv')
# df2 = pd.read_csv('DXSUM_PDXCONV_ADNIALL.csv')

# df3 = pd.read_csv('sorted_nc2_old1.csv')
# df3['EXAMDATE'] = ""
# df3["Age"] = ""
# df3['study'] = ""
# for row in df3.itertuples(index=False):
#     subjid = row[df3.columns.get_loc('Subject ID')]
#     filterdf = df2[df2.PTID == subjid]
#     rid = filterdf['RID'].iloc[0]
#     examdate = filterdf['EXAMDATE'].iloc[0]
#     phase = filterdf['Phase'].iloc[0]

#     df3.loc[df3['Subject ID'] == subjid, 'RID'] = rid
#     df3.loc[df3['Subject ID'] == subjid, 'EXAMDATE'] = examdate
#     df3.loc[df3['Subject ID'] == subjid, 'study'] = phase

#     filterdf2 = df1[df1.Subject == subjid]
#     age = filterdf2['Age'].iloc[0]
#     df3.loc[df3['Subject ID'] == subjid, 'Age'] = age

#     #print(f'{rid}')
# df3.to_csv('sorted_nc2.csv', index=False)


df1 = pd.read_csv('sorted_ad2.csv')
df2 = pd.read_csv('sorted_nc2.csv')
df = df1.append(df2, ignore_index=True)
df.to_csv('csvs/overview_subjects2.csv', index=False)