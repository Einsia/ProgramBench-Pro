"""Decoded low-resolution whole-image evidence, independent of compressed bytes."""
import io,json,sys
from PIL import Image,ImageOps
image=Image.open(io.BytesIO(sys.stdin.buffer.read()))
fmt=image.format
image=ImageOps.exif_transpose(image).convert('RGB')
grid=image.resize((24,32),Image.Resampling.BOX)
print(json.dumps({'format':fmt,'size':list(image.size),'pixels':[list(x) for x in grid.getdata()]}))
