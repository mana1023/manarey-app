from pathlib import Path

p = Path("models/stock_model.py")
s = p.read_text(encoding="utf-8")

count_dq = s.count('"""')
count_sq = s.count("'''")
print("count_dq=", count_dq, "count_sq=", count_sq)

# find first unclosed triple quote naive: scan and toggle
positions = []
for token in ['"""', "'''"]:
    idx = 0
    occ = []
    while True:
        i = s.find(token, idx)
        if i == -1:
            break
        occ.append(i)
        idx = i + 3
    print(token, "occurrences=", len(occ))
    # print first few contexts
    for i in occ[:5]:
        print("pos", i, "context:", repr(s[i - 40 : i + 40]))

# show tail
print("tail repr", repr(s[-400:]))
