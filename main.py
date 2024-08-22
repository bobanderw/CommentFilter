import pandas as pd

from is_comment import judge_comment

data = pd.read_csv("data.csv")


for index, row in data.iterrows():
    print(f"Processing row {index+1} of {len(data)}")
    try:
         category = judge_comment(row['content'])
         if category:
             data.at[index, 'category'] = category
         else:
             data.at[index, 'category'] = ""
    except Exception as e:
        print(e)
        data.at[index, 'category'] = "error"

data.to_csv("data_with_category.csv", index=False, encoding='utf-8')


# if __name__ == "__main__":
#     ret = judge_comment("""
#         #广州电费#  公寓的空调3级能耗， 好家伙，一个月电费600块， 上班族晚上使用，这个费用，懂得都懂。 @魔方公寓 
#     """)
#     print(ret)