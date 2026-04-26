p = r"c:\\Users\\USUARIO\\Desktop\\Manarey\\models\\stock_model.py"
s = open(p, "r", encoding="utf-8").read()
idx = s.find("def get_queue_items")
print("idx", idx)
print("---CTX---")
print(s[max(0, idx - 200) : idx + 200])
