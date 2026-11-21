import asyncio, json, edge_tts, subprocess, sys
VOICE = sys.argv[1] if len(sys.argv)>1 else "en-IN-NeerjaExpressiveNeural"
FF="/Users/azim/dotandkey-hackathon/.venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
async def one(key, text):
    c = edge_tts.Communicate(text, VOICE, rate="+12%", boundary="WordBoundary")
    words=[]; audio=b""
    async for ch in c.stream():
        if ch["type"]=="audio": audio+=ch["data"]
        elif ch["type"]=="WordBoundary": words.append([ch["offset"]/1e7, (ch["offset"]+ch["duration"])/1e7, ch["text"]])
    open(f"vo/{key}.mp3","wb").write(audio)
    subprocess.run([FF,"-y","-loglevel","error","-i",f"vo/{key}.mp3","-ar","48000","-ac","2",f"vo/{key}.wav"],check=True)
    return key, words
async def main():
    lines=json.load(open("vo.json")); out={}
    for k,t in lines:
        k,w = await one(k,t); out[k]=w
        print(k, round(w[-1][1],2), "s", len(t.split()), "words")
    json.dump(out, open("vo/words.json","w"))
    print("TOTAL", round(sum(v[-1][1] for v in out.values()),1))
asyncio.run(main())
