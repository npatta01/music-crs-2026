"""Assemble training data for the request-conditioned dual-encoder retriever.
Per train turn: query variants (last msg / last-3 / +played titles) + positive track text +
hard-negative track texts. From existing artifacts (train_negatives_full + train sessions + catalog).
No future-turn / GT leakage."""
import sys, json, ast
sys.path.insert(0,"scripts/rerank")
import lancedb
from datasets import load_dataset
# catalog text
db=lancedb.connect("cache/lancedb"); t=db.open_table("music_track_catalog")
txt={}
for r in t.search().select(["track_id","track_name","artist_name","release_date","tag_list"]).limit(60000).to_list():
    nm=r.get("track_name"); nm=(nm[0] if isinstance(nm,list) and nm else nm) or ""
    ar=r.get("artist_name"); ar=(ar[0] if isinstance(ar,list) and ar else ar) or ""
    yr=str(r.get("release_date") or "")[:4]; tags=", ".join((r.get("tag_list") or [])[:10])
    txt[str(r["track_id"])]=f"{ar} - {nm} | {yr} | {tags}"
print(f"catalog text: {len(txt)}",flush=True)
# train sessions: user messages + played history
ds=load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="train")
umsg={}; played={}
for r in ds:
    conv=r.get("conversations")
    if isinstance(conv,str): conv=ast.literal_eval(conv)
    sid=str(r["session_id"]); um={}; pl={}
    for m in conv:
        tn=int(m["turn_number"])
        if m["role"]=="user": um[tn]=str(m["content"])
        elif m["role"]=="music": pl.setdefault(tn,[]).append(str(m["content"]))
    umsg[sid]=um; played[sid]=pl
print(f"train sessions: {len(umsg)}",flush=True)
out=open("exp/analysis/retrieval_exploration/retriever_train_data.jsonl","w"); n=0
for line in open("exp/analysis/rerank/train_negatives_full.jsonl"):
    d=json.loads(line); sid=d["session_id"]; tn=int(d["turn_number"]); g=str(d["gt"])
    if g not in txt: continue
    um=umsg.get(sid,{}); pl=played.get(sid,{})
    q_last=um.get(tn,"")
    q_ctx=" | ".join(um.get(k,"") for k in (tn-2,tn-1,tn) if um.get(k))
    prev_titles=[txt.get(x,"").split(" | ")[0] for k in range(1,tn) for x in pl.get(k,[]) if x in txt][-5:]
    hard=[txt[h["id"]] for h in d["hard_negatives"] if h["id"] in txt][:8]
    rec={"sid":sid,"tn":tn,"q_last":q_last,"q_ctx":q_ctx,"played":prev_titles,
         "pos":txt[g],"negs":hard}
    out.write(json.dumps(rec)+"\n"); n+=1
    if n%20000==0: print(f"  {n}",flush=True)
out.close(); print(f"DONE wrote {n} -> retriever_train_data.jsonl",flush=True)
