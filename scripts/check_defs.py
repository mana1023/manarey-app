with open("models/stock_model.py", "r", encoding="utf-8") as f:
    s = f.read()
print("enqueue_op idx=", s.find("def enqueue_op"))
print("get_queue_items idx=", s.find("def get_queue_items"))
idx = s.find("def enqueue_op")
if idx != -1:
    print("enqueue_op sample:", repr(s[max(0, idx - 80) : idx + 120]))
else:
    print("enqueue_op not found")
