import sys, subprocess, os
from PIL import Image
FF="/Users/azim/dotandkey-hackathon/.venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
src, out, every = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv)>3 else 1.5
tmp=out+"_tmp"; os.makedirs(tmp, exist_ok=True)
for f in os.listdir(tmp): os.remove(os.path.join(tmp,f))
subprocess.run([FF,"-loglevel","error","-i",src,"-vf",f"fps=1/{every},scale=480:-1",os.path.join(tmp,"%03d.png")],check=True)
fs=sorted(os.listdir(tmp)); cols=4; rows=(len(fs)+cols-1)//cols
sheet=Image.new("RGB",(480*cols,270*rows),"white")
for i,f in enumerate(fs): sheet.paste(Image.open(os.path.join(tmp,f)),((i%cols)*480,(i//cols)*270))
sheet.save(out); print(out, len(fs))
