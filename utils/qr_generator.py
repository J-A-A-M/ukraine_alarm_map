import qrcode
from PIL import Image, ImageDraw, ImageFont

# Define the URL and the text you want to encode
url = "https://github.com/J-A-A-M/ukraine_alarm_map"
text = "Scan me to visit Example.com"

# Create a QR code object
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

# Add data to the QR code
qr.add_data(url)
qr.make(fit=True)

# Create an image from the QR code instance
img = qr.make_image(fill="black", back_color="white")

# Convert image to RGBA to add transparency
img = img.convert("RGBA")

# Make the white background transparent
data = img.getdata()
new_data = []
for item in data:
    if item[:3] == (255, 255, 255):
        new_data.append((255, 255, 255, 0))
    else:
        new_data.append(item)

img.putdata(new_data)

# Load a font
font = ImageFont.load_default()

# Get the size of the text
draw = ImageDraw.Draw(img)
text_width, text_height = draw.textsize(text, font)

# Create a new image that includes space for the text
total_height = img.size[1] + text_height + 10  # 10 pixels of padding
new_img = Image.new("RGBA", (img.size[0], total_height), (255, 255, 255, 0))

# Paste the QR code image on the new image
new_img.paste(img, (0, 0))

# Draw the text on the new image
draw = ImageDraw.Draw(new_img)
text_position = ((new_img.size[0] - text_width) // 2, img.size[1] + 5)
draw.text(text_position, text, font=font, fill="black")

# Save the image to a file
new_img.save("website_qr_with_text.png")

print("QR code with text below generated and saved as 'website_qr_with_text.png'")
