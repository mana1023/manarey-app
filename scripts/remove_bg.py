import os

from PIL import Image


def remove_white_bg(img_path, t=230):
    if not os.path.exists(img_path):
        return
    img = Image.open(img_path).convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[0] > t and item[1] > t and item[2] > t:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    img.save(img_path, "PNG")
    print(f"Removed white bg from {img_path}")


def remove_black_bg(img_path, t=30):
    if not os.path.exists(img_path):
        return
    img = Image.open(img_path).convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[0] < t and item[1] < t and item[2] < t:
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)

    # ensure it is saved as PNG if it was JPG
    new_path = img_path
    if img_path.lower().endswith(".jpg"):
        new_path = img_path[:-4] + ".png"
    img.save(new_path, "PNG")
    print(f"Removed black bg from {img_path} -> {new_path}")


base = "c:/Users/USUARIO/Desktop/Manarey/assets/images"
remove_white_bg(f"{base}/logo_manarey.png")
remove_white_bg(f"{base}/logo_manarey_brand.png")
remove_black_bg(f"{base}/menu_footer.jpg")
